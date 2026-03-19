import io

import torch
from metaflow import S3
from torch.utils.data import DataLoader, TensorDataset
from torchvision import datasets


TRAIN_KEY = "fashion-mnist/train.pt"
TEST_KEY = "fashion-mnist/test.pt"


def _dataset_to_tensors(dataset):
    images = dataset.data.float().unsqueeze(1) / 255.0
    labels = dataset.targets
    return images, labels


def download_and_upload_to_s3(s3_root):
    train_ds = datasets.FashionMNIST(root="/tmp/fmnist", train=True, download=True)
    test_ds = datasets.FashionMNIST(root="/tmp/fmnist", train=False, download=True)

    train_images, train_labels = _dataset_to_tensors(train_ds)
    test_images, test_labels = _dataset_to_tensors(test_ds)

    with S3(s3root=s3_root) as s3:
        for key, tensors in [
            (TRAIN_KEY, (train_images, train_labels)),
            (TEST_KEY, (test_images, test_labels)),
        ]:
            buf = io.BytesIO()
            torch.save(tensors, buf)
            s3.put(key, buf.getvalue())


def data_exists_in_s3(s3_root):
    with S3(s3root=s3_root) as s3:
        objs = s3.list_paths([TRAIN_KEY, TEST_KEY])
        return len(objs) == 2


def load_from_s3(s3_root):
    with S3(s3root=s3_root) as s3:
        results = {}
        for key in [TRAIN_KEY, TEST_KEY]:
            obj = s3.get(key)
            buf = io.BytesIO(open(obj.path, "rb").read())
            images, labels = torch.load(buf, weights_only=True)
            results[key] = (images, labels)
    return results[TRAIN_KEY], results[TEST_KEY]


def create_dataloaders(train_data, test_data, batch_size):
    train_images, train_labels = train_data
    test_images, test_labels = test_data

    train_loader = DataLoader(
        TensorDataset(train_images, train_labels),
        batch_size=batch_size,
        shuffle=True,
    )
    test_loader = DataLoader(
        TensorDataset(test_images, test_labels),
        batch_size=batch_size,
        shuffle=False,
    )
    return train_loader, test_loader
