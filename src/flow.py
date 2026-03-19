import io
import os
import random

import numpy as np
import torch
from dotenv import load_dotenv

load_dotenv()

import torch.nn as nn
import wandb
from metaflow import FlowSpec, Parameter, environment, resources, step

from data import create_dataloaders, data_exists_in_s3, download_and_upload_to_s3, load_from_s3
from model import FashionCNN


class TrainingFlow(FlowSpec):
    data_bucket = Parameter(
        "data-bucket",
        help="S3 bucket name for Fashion-MNIST data",
        envvar="DATA_BUCKET",
        required=True,
    )

    data_prefix = Parameter(
        "data-prefix",
        help="S3 key prefix for Fashion-MNIST data",
        envvar="DATA_PREFIX",
        default="fashion-mnist-data",
    )

    @step
    def start(self):
        self.learning_rates = [0.001, 0.01, 0.1]
        self.batch_size = 64
        self.num_epochs = 10
        self.wandb_project = "rapid-ml-ops-demo"
        self.s3_root = f"s3://{self.data_bucket}/{self.data_prefix}"

        print(f"Training config: LRs={self.learning_rates}, "
              f"batch_size={self.batch_size}, epochs={self.num_epochs}")
        print(f"Data location: {self.s3_root}")

        self.next(self.data_validation)

    @step
    def data_validation(self):
        if data_exists_in_s3(self.s3_root):
            print("Fashion-MNIST data found in S3, skipping download.")
        else:
            print("Fashion-MNIST data not found in S3, downloading and uploading...")
            download_and_upload_to_s3(self.s3_root)
            print("Upload complete.")

        self.next(self.train, foreach="learning_rates")

    @environment(vars={"WANDB_API_KEY": os.environ.get("WANDB_API_KEY", "")})
    @resources(gpu=1, cpu=4, memory=14000)
    @step
    def train(self):
        lr = self.input

        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Training with lr={lr} on {device}")

        train_data, test_data = load_from_s3(self.s3_root)
        train_loader, test_loader = create_dataloaders(
            train_data, test_data, self.batch_size
        )

        model = FashionCNN().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        run = wandb.init(
            project=self.wandb_project,
            name=f"lr-{lr}",
            config={
                "learning_rate": lr,
                "batch_size": self.batch_size,
                "epochs": self.num_epochs,
                "architecture": "FashionCNN",
            },
        )

        for epoch in range(self.num_epochs):
            # Train
            model.train()
            train_loss, train_correct, train_total = 0.0, 0, 0
            for images, labels in train_loader:
                images, labels = images.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item() * images.size(0)
                train_correct += (outputs.argmax(1) == labels).sum().item()
                train_total += images.size(0)

            # Evaluate
            model.eval()
            val_loss, val_correct, val_total = 0.0, 0, 0
            with torch.no_grad():
                for images, labels in test_loader:
                    images, labels = images.to(device), labels.to(device)
                    outputs = model(images)
                    loss = criterion(outputs, labels)
                    val_loss += loss.item() * images.size(0)
                    val_correct += (outputs.argmax(1) == labels).sum().item()
                    val_total += images.size(0)

            train_acc = train_correct / train_total
            val_acc = val_correct / val_total

            wandb.log({
                "epoch": epoch + 1,
                "train_loss": train_loss / train_total,
                "train_accuracy": train_acc,
                "val_loss": val_loss / val_total,
                "val_accuracy": val_acc,
            })

            print(f"Epoch {epoch + 1}/{self.num_epochs} - "
                  f"train_acc: {train_acc:.4f}, val_acc: {val_acc:.4f}")

        self.val_accuracy = val_acc
        self.lr = lr

        buf = io.BytesIO()
        torch.save(model.state_dict(), buf)
        self.model_state = buf.getvalue()

        wandb.log({"final_val_accuracy": val_acc})
        run.finish()

        print(f"Finished training lr={lr}, val_accuracy={val_acc:.4f}")
        self.next(self.pick_best)

    @environment(vars={"WANDB_API_KEY": os.environ.get("WANDB_API_KEY", "")})
    @step
    def pick_best(self, inputs):
        results = [
            {"lr": inpt.lr, "val_accuracy": inpt.val_accuracy, "model_state": inpt.model_state}
            for inpt in inputs
        ]

        for r in results:
            print(f"  lr={r['lr']}: val_accuracy={r['val_accuracy']:.4f}")

        best = max(results, key=lambda r: r["val_accuracy"])
        self.best_lr = best["lr"]
        self.best_val_accuracy = best["val_accuracy"]

        print(f"Best model: lr={self.best_lr}, val_accuracy={self.best_val_accuracy:.4f}")

        # Register best model as wandb artifact
        run = wandb.init(
            project=inputs[0].wandb_project,
            name="register-best-model",
            job_type="model-registry",
        )
        artifact = wandb.Artifact(
            name="fashion-cnn-best",
            type="model",
            metadata={"learning_rate": self.best_lr, "val_accuracy": self.best_val_accuracy},
        )
        with artifact.new_file("model.pt", mode="wb") as f:
            f.write(best["model_state"])
        run.log_artifact(artifact)
        artifact.wait()
        try:
            run.link_artifact(artifact, target_path="wandb-registry-model/fashion-cnn-best")
            print("Model linked to wandb registry.")
        except Exception as e:
            print(f"Warning: could not link artifact to registry: {e}")
        run.finish()

        # Merge required attributes from one of the inputs
        self.s3_root = inputs[0].s3_root
        self.batch_size = inputs[0].batch_size
        self.num_epochs = inputs[0].num_epochs
        self.wandb_project = inputs[0].wandb_project
        self.learning_rates = inputs[0].learning_rates

        self.next(self.end)

    @step
    def end(self):
        print("=" * 50)
        print("Training Flow Complete")
        print(f"  Best learning rate: {self.best_lr}")
        print(f"  Best val accuracy:  {self.best_val_accuracy:.4f}")
        print(f"  wandb project:      {self.wandb_project}")
        print("=" * 50)


if __name__ == "__main__":
    TrainingFlow()
