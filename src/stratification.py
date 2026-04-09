"""
Currently, we are implementing a modification of the algorithm as described in Sechidis et al. [1].
This involves stratifying multi-label data to maintain label distributions across splits.

In the future, we may also add a label combination parameter as described in Szymanski et al. [2],
which enables better handling of imbalanced datasets.

## Algorithm differences from Sechidis et al. [1]:

** Order in Which Groups are Assigned to Partitions: **
In the paper, every record is considered individually, and so it can only have at most 1 evidence for the column in
question. So the original method assigns the rows arbitrarily (e.g. in the order which they occur top to bottom). Each
record goes to the partition which still needs the most evidence for that label column. However, we have groups that are
being assigned, and each group can have any amount of evidence. The order in which groups are assigned now becomes
extremely important.

If we were to assign the groups with the least amount of evidence first, then all the small groups would be assigned
to the group needing a lot of evidence for that label column. When we come to the end of assigning groups with evidence
for that column, we may be left with a single group containing a large amount of evidence, but two partitions that each
need only a small amount of evidence. Assigning the large group to one of the two partitions would result in one
partition with far more evidence than it needs (and possibly a disproportionate quantity of records in general), and
another partition that is significantly short of evidence. This results in a large amount of error (deviation from
desired quantity) that could be avoided if we instead had placed the large group in the partition needing the most
evidence.

If we assign the largest group first, the possibilities are much better. If there are partitions with a large amount of
needed evidence, then we will more quickly balance those partitions. Even in the case where a large group contains more
evidence than any single partition needs, it will at least be placed into the partition which would result in the least
error for having that group included. The other partitions which are already close to the desired quantity will then be
assigned smaller groups which result in smaller error for those groups.

** Dummy Column **
The original algorithm finishes with "distributing negative evidence." That is, it takes all records where the value of
all columns is 0 and assigns them randomly to the various partitions based on how many records each partitions needs.
Our modified algorithm also needs to take the size of the group into account. We could do this by writing separate code
to select partitions and groups based on size, but that code would be similar to our code for assigning positive
evidence, except for size rather than "quantity of evidence." However, if we add another column to the Y matrix with all
positive values (1.0), then when the algorithm calculates "quantity of evidence" for that column it will actually be
calculating the number of records. And the "fraction of evidence" that is required for each partition will actually be
the number of records that need to go into the partition.

Since our algorithm chooses the order of columns to consider based on "least evidence first," that means that the dummy
column will be the last considered, and the only groups assigned based on that column will be the ones which do not have
any other positive markers. That is, it will be the records that are "negative evidence" for all categories.

** Implementation note **
The algorithm is greedy. It does a good job balancing each piece of evidence individually. However, the joint distribution
of multiple columns will not be balanced.

Say we have equal samples of two boolean columns (A, B), so we end up with 25% each of
* (0, 0)
* (0, 1)
* (1, 0)
* (1, 1)

If we want a 50-50 split for each of A and B, we would like each split to be have the same 25% of the joint (A, B),
Instead, we can end up with
split_1: 100% of each of (0, 0) and (1, 1)
split_2: 100% of each of (0, 1) and (1, 0)

The marginal distributions are correct, split_1 has 50% A and B, where we would have liked
split_1: 50% of each of (0, 0), (0, 1), (1, 0) and (1, 1)
split_2: 50% of each of (0, 0), (0, 1), (1, 0) and (1, 1)

==================== Bibliography ====================
References
----------
[1] Sechidis, K., Tsoumakas, G., & Vlahavas, I. (2011). On the stratification of multi-label data. Machine Learning and
Knowledge Discovery in Databases, 145–158. Springer. http://lpis.csd.auth.gr/publications/sechidis-ecmlpkdd-2011.pdf

[2] Szymański, P., & Kajdanowicz, T. (2017). A network perspective on stratification of multi-label data. Proceedings of
the First International Workshop on Learning with Imbalanced Domains: Theory and Applications, 22–35. PMLR.
http://proceedings.mlr.press/v74/szyma%C5%84ski17a.html

"""

import logging
import math
import time
from collections import defaultdict
from random import Random
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.Logger(__name__)


class IterativelyStratifiedGroupPartition:
    """A set of partitions using iterative stratification."""

    def __init__(
        self,
        Y,
        groups=None,
        n_splits: int | None = None,
        sample_distribution_per_fold: list[float] | None = None,
        random_state: int | None = None,
        raise_if_infeasible: bool = False,
    ):
        """
        Parameters
        ----------
        Y : array-like of shape (n_samples, n_labels)
            Unedited Y from constructor

        groups : array-like of shape (n_samples,)
            Integers indicating which group a record belongs to. Must be the same length as Y.

        n_splits : int | None
            If supplied, will determine the number of equal-sized partitions to divide the data into.
            Must be greater than 1. For example, `n_splits=3` will create 3 partitions of (approximately)
            equal size.

        sample_distribution_per_fold : list[float] | None
            If supplied, defines the relative sizes of the partitions. The list must sum to 1.0.
            For example, `sample_distribution_per_fold=[0.2, 0.3, 0.5]` will create partitions where
            20%, 30%, and 50% of the data are assigned to the respective folds.

        random_state : int | None
            A seed for the random number generator to ensure reproducible results. If `None`,
            a random seed will be generated automatically.

        raise_if_infeasible : bool
            If set to True, raises an exception when the input data cannot satisfy the constraints
            for stratified group partitioning. If False, warnings will be logged.
        """

        match Y:
            case pd.DataFrame():
                Y = Y.to_numpy()
            case pd.Series():
                Y = Y.to_numpy().reshape(-1, 1)
            case np.ndarray():
                pass
            case _:
                raise ValueError(
                    f"Y must be an array-like object, either a pandas DataFrame, pandas Series, or numpy ndarray."
                )

        # Add a dummy column so that all groups get assigned even if some groups are negative on all evidence columns
        dummy_col = np.ones((Y.shape[0], 1))
        Y = np.append(Y, dummy_col, axis=1)

        if not random_state:
            random_state = time.monotonic_ns()

        logger.info(f"Using random_state: {random_state}")

        # Data validation on groups and sample_distribution_per_fold
        self._group_to_indices = self._assign_rows_to_groups(len(Y), groups)
        self._partition_sizes = self._determine_partition_sizes(n_splits, sample_distribution_per_fold)

        # Preprocess "evidence" into useful data structures. See [1] for description of "evidence"
        self._total_evidence: np.ndarray = Y.sum(axis=0)
        self._evidence_desired_by_partition: list[np.ndarray] = [
            fraction * self._total_evidence for fraction in self._partition_sizes
        ]
        self._group_to_evidence = self._compute_evidence_vector_by_group(Y, self._group_to_indices)

        # Primary workload
        self._partitions = self._generate_partitions(
            self._total_evidence,
            self._evidence_desired_by_partition,
            self._group_to_evidence,
            self._group_to_indices,
            random_state,
            raise_if_infeasible,
        )

    @staticmethod
    def _determine_partition_sizes(
        n_splits: int | None, sample_distribution_per_fold: list[float] | None
    ) -> list[float]:
        """Based on inputs, generate a normalized list of the ideal fraction of records in each partition."""

        if (n_splits and n_splits == 1) or (sample_distribution_per_fold and len(sample_distribution_per_fold) == 1):
            raise ValueError("The number of splits must be more than 1.")

        if n_splits and not sample_distribution_per_fold:
            return [1 / n_splits] * n_splits

        elif sample_distribution_per_fold and not n_splits:
            if len(sample_distribution_per_fold) < 2:
                raise ValueError("The length of sample_distribution_per_fold must be at least 2. ")

            if not math.isclose(sum(sample_distribution_per_fold), 1.0):
                raise ValueError(
                    "The values in sample_distribution_per_fold must sum to 1.0 if n_splits is not supplied. "
                )
            return sample_distribution_per_fold

        else:
            raise ValueError("Please supply exactly one of n_splits or sample_distribution_per_fold.")

    @staticmethod
    def _assign_rows_to_groups(n_samples: int, groups: Iterable[int]) -> dict[int, list[int]]:

        if n_samples != len(groups):
            raise ValueError("The length of the groups vector must match the number of rows in Y.")

        group_to_indices = defaultdict(list)
        for i, group_id in enumerate(groups):
            group_to_indices[group_id].append(i)

        return group_to_indices

    @staticmethod
    def _compute_evidence_vector_by_group(
        Y: np.ndarray, group_to_indices: dict[int, list[int]]
    ) -> dict[int, np.ndarray]:
        return {group_id: Y[indices].sum(axis=0) for group_id, indices in group_to_indices.items()}

    @staticmethod
    def _columns_in_order_of_assignment(total_evidence_vector: np.ndarray) -> list[int]:
        """
        Column numbers in the order in which evidence should be assigned.

        We want to start by assigning evidence for the column with the least available evidence. Then the next least,
        and so on. However, columns with no evidence don't have anything to distribute so we exclude those.

        Parameters
        ----------
        total_evidence_vector : np.ndarray
            An array of numeric values indicating the total evidence available for each label.
        """
        evidence_and_column = sorted(
            [
                (quantity_of_evidence, column_number)
                for column_number, quantity_of_evidence in enumerate(total_evidence_vector)
                if quantity_of_evidence > 0
            ]
        )

        return [element[1] for element in evidence_and_column]

    @staticmethod
    def _groups_in_order_of_assignment(column_id: int, group_to_evidence: dict[int, np.ndarray]) -> list[int]:
        """
        Group IDs with evidence in column_id, in the order in which they should be assigned.

        Groups are assigned in the order of groups with most evidence first. For information on the reasoning for this
        decision, see the section "Order in Which Groups are Assigned to Partitions" in the module level docstring.
        Groups with no evidence for this label are not included in the list.
        """
        evidence_and_group = sorted(
            [
                (evidence_vector[column_id], group_id)
                for group_id, evidence_vector in group_to_evidence.items()
                if evidence_vector[column_id] > 0
            ],
            reverse=True,
        )

        return [element[1] for element in evidence_and_group]

    @staticmethod
    def _determine_assignment_partition(
        evidence_desired_by_partition: list[np.ndarray],
        column_id: int,
        random: Random,
    ):
        """
        Return the partition number that the next group should be assigned to.

        For a given column of the label matrix, determine which partition still needs the most evidence for that column.
        If more than one partition are tied for the most evidence still required, then one of them is selected at
        random.

        Parameters
        ----------
        evidence_desired_by_partition : list[np.ndarray]
            A list with the ndarray indicating the amount of evidence still required for each partition.

        column_id: int
            The column of labels currently being distributed.

        random: Random
            A random number generator used for breaking ties.
        """
        largest_observed_evidence_needed = float("-inf")
        partitions_needing_that_evidence = list()

        for partition_number, needed_evidence_vector in enumerate(evidence_desired_by_partition):

            evidence_needed = needed_evidence_vector[column_id]

            if evidence_needed > largest_observed_evidence_needed:
                largest_observed_evidence_needed = evidence_needed
                partitions_needing_that_evidence = [partition_number]

            elif evidence_needed == largest_observed_evidence_needed:
                partitions_needing_that_evidence.append(partition_number)

        if len(partitions_needing_that_evidence) > 1:
            result = random.choice(partitions_needing_that_evidence)
        else:
            result = partitions_needing_that_evidence[0]

        return result

    @staticmethod
    def _all_groups_have_some_evidence(
        evidence_desired_by_partition: list[np.ndarray], remaining_evidence_desired_by_partition: list[np.ndarray]
    ) -> bool:
        """Determines whether all partitions have been assigned at least some evidence for all label columns.

        If a label column has no evidence, then it is skipped for the sake of this check.
        """
        for evidence_vector, remaining_evidence_vector in zip(
            evidence_desired_by_partition, remaining_evidence_desired_by_partition
        ):
            for column_value, remaining_column_value in zip(evidence_vector, remaining_evidence_vector):
                if 0 < column_value == remaining_column_value:
                    return False

        return True

    @classmethod
    def _generate_partitions(
        cls,
        total_evidence: np.ndarray,
        evidence_desired_by_partition: list[np.ndarray],
        group_to_evidence: dict[int, np.ndarray],
        group_to_indices: dict[int, list[int]],
        random_state: int,
        raise_if_infeasible: bool,
    ) -> list[list[int]]:
        """Assign all indices to partitions.

        Parameters
        ----------
        total_evidence : np.ndarray
            the vector of total evidence for the entire dataset.

        evidence_desired_by_partition : list[np.ndarray]
            list of the evidence vector that each partition should have

        group_to_evidence : dict[int, np.ndarray]
            dict mapping group_id to the evidence vector contained in that group

        random_state: int
            integer seed for the random number generator to ensure reproducible results.

        raise_if_infeasible: bool
            If True an ExceptionGroup will be raised with any failed quality checks

        Returns
        -------
        partitions : list[list[int]]
            a list where every element is a list containing the indices that belong to that partition.
        """
        partitions = [[] for _ in range(len(evidence_desired_by_partition))]
        random = Random(random_state)

        # Copy data structures to avoid mutating external state
        remaining_evidence_desired_by_partition = [evidence.copy() for evidence in evidence_desired_by_partition]

        # Primary logic to assign records to partitions
        groups_assigned = set()
        for column_id in cls._columns_in_order_of_assignment(total_evidence):
            for group_id in cls._groups_in_order_of_assignment(column_id, group_to_evidence):
                if group_id in groups_assigned:
                    continue

                # Figure out which partition is going to get the next evidence
                partition_id = cls._determine_assignment_partition(
                    remaining_evidence_desired_by_partition, column_id, random
                )

                # Add the current group's row numbers to that partition
                partitions[partition_id].extend(group_to_indices[group_id])

                # Adjust the partition's evidence vector to reflect the new contents
                remaining_evidence_desired_by_partition[partition_id] -= group_to_evidence[group_id]

                # Mark the group as "assigned" so we don't assign it again
                groups_assigned.add(group_id)

        validation_errors = []
        if not cls._all_groups_have_some_evidence(
            evidence_desired_by_partition, remaining_evidence_desired_by_partition
        ):
            validation_errors.append(ValueError("Not all partitions received evidence for all labels."))

        if raise_if_infeasible and len(validation_errors) > 0:
            raise ExceptionGroup("Errors in validating resulting partitions:", validation_errors)

        return partitions

    @property
    def partitions(self) -> list[list[int]]:
        """The row indices for each partition."""
        return [x.copy() for x in self._partitions]
