import copy
from typing import List
from typing import Tuple
from typing import Union

import syft as sy
from syft.generic.frameworks.types import FrameworkTensorType
from syft.generic.tensor import AbstractTensor
from syft.messaging.plan.state import State
from syft.workers.abstract import AbstractWorker


class Procedure(object):
    """
    A Procedure is a wrapper over a list of operations to execute.

    It provides tools to update the operations to un with new arguments
    on different workers.

    Args:
        operations: the list of (serialized) operations
        arg_ids: the argument ids present in the operations
        result_ids: the result ids present in the operations
    """

    def __init__(self, operations=None, arg_ids=None, result_ids=None):
        self.operations = operations or []
        self.arg_ids = arg_ids or []
        self.result_ids = result_ids or []
        # promise_out_id id used for plan augmented to be used with promises
        self.promise_out_id = None

    def __str__(self):
        return f"<Procedure #operations:{len(self.operations)}>"

    def __repr__(self):
        return self.__str__()

    def update_args(
        self,
        args: Tuple[Union[FrameworkTensorType, AbstractTensor]],
        result_ids: List[Union[str, int]],
    ):
        """Replace args and result_ids with the ones given.
        Updates the arguments ids and result ids used to execute
        the plan.
        Args:
            args: List of tensors.
            result_ids: Ids where the plan output will be stored.
        """

        arg_ids = tuple(arg.id for arg in args)
        self.update_ids(self.arg_ids, arg_ids)
        self.arg_ids = arg_ids

        self.update_ids(self.result_ids, result_ids)
        self.result_ids = result_ids

    def update_worker_ids(self, from_worker_id: Union[str, int], to_worker_id: Union[str, int]):
        return self.update_ids([], [], from_worker_id, to_worker_id)

    def update_ids(
        self,
        from_ids: Tuple[Union[str, int]] = [],
        to_ids: Tuple[Union[str, int]] = [],
        from_worker: Union[str, int] = None,
        to_worker: Union[str, int] = None,
    ):
        """Replace ids and worker ids in the list of operations stored

        Args:
            from_ids: Ids to change.
            to_ids: Ids to replace with.
            from_worker: The previous worker that built the plan.
            to_worker: The new worker that is running the plan.
        """

        # We operate on simplified content of Operation, hence all values should be simplified
        from_workers_simplified = None
        to_workers_simplified = None
        if from_worker and to_worker:
            from_workers_simplified = [sy.serde._simplify(None, from_worker)]
            to_workers_simplified = [sy.serde._simplify(None, to_worker)]

        from_ids_simplified = None
        to_ids_simplified = None
        if len(from_ids) and len(to_ids):
            from_ids_simplified = [sy.serde._simplify(None, id) for id in from_ids]
            to_ids_simplified = [sy.serde._simplify(None, id) for id in to_ids]

        for idx, operation in enumerate(self.operations):
            if from_workers_simplified and to_workers_simplified:
                operation = Procedure.replace_operation_ids(
                    operation, from_workers_simplified, to_workers_simplified
                )

            if from_ids_simplified and to_ids_simplified:
                operation = Procedure.replace_operation_ids(
                    operation, from_ids_simplified, to_ids_simplified
                )

            self.operations[idx] = operation

        return self

    @staticmethod
    def replace_operation_ids(operation, from_ids, to_ids):
        """
        Replace ids in a single operation

        Args:
            operation: the operation to update
            from_ids: the ids to replace
            to_ids: the new ids to put inplace
        """

        assert isinstance(from_ids, (list, tuple))
        assert isinstance(to_ids, (list, tuple))

        type_obj = type(operation)
        operation = list(operation)
        for i, item in enumerate(operation):
            # Since this is simplified content, id can be int or simplified str (tuple)
            if isinstance(item, (int, tuple)) and item in from_ids:
                operation[i] = to_ids[from_ids.index(item)]
            elif isinstance(item, (list, tuple)):
                operation[i] = Procedure.replace_operation_ids(
                    operation=item, from_ids=from_ids, to_ids=to_ids
                )
        return type_obj(operation)

    def copy(self) -> "Procedure":
        procedure = Procedure(
            operations=copy.deepcopy(self.operations),
            arg_ids=self.arg_ids,
            result_ids=self.result_ids,
        )
        return procedure

    @staticmethod
    def simplify(worker: AbstractWorker, procedure: "Procedure") -> tuple:
        return (
            # We're not simplifying fully because operations are already simplified
            sy.serde._simplify(worker, procedure.operations, shallow=True),
            sy.serde._simplify(worker, procedure.arg_ids),
            sy.serde._simplify(worker, procedure.result_ids),
            sy.serde._simplify(worker, procedure.promise_out_id),
        )

    @staticmethod
    def detail(worker: AbstractWorker, procedure_tuple: tuple) -> "State":
        operations, arg_ids, result_ids, promise_out_id = procedure_tuple

        operations = sy.serde._detail(worker, operations, shallow=True)
        arg_ids = sy.serde._detail(worker, arg_ids)
        result_ids = sy.serde._detail(worker, result_ids)

        procedure = Procedure(operations, arg_ids, result_ids)
        procedure.promise_out_id = promise_out_id
        return procedure
