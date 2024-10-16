"""
File containing the class of the quantum convolutional neural network method. The class of this classifier and its method are all in this file.
The function that runs the main algorithm is the .run method.
"""

from pennylane import numpy as np
from numpy.typing import NDArray
from typing import Tuple, List
import pennylane as qml
from utils.utils import get_qnode_instance, get_score
from utils.error_functions import mean_square_error


class QCNN_Solver:
    def __init__(
        self,
        embedding_circuit: callable,
        num_qubits: int,
    ) -> None:
        """
        Object that can run the quantum convolutional neural network classification algorithm. It must use the Pennylane architecture to create the circuit.

        Parameters:
        - embedding_circuit (callable): The Python function describing the embedding circuit of the data.
        - num_qubits (int): The number of qubits of the embedding circuit and the ansatz.

        Returns:
        None
        """
        self.embedding = embedding_circuit
        self.num_qubits = num_qubits
        self.circuit_to_optimize = get_qnode_instance(
            self.generate_qcnn_circuit, self.num_qubits
        )
        self.num_qubits

        # get the number of parameters
        self.num_params = 0
        test_qubits = self.num_qubits
        while test_qubits > 1:
            self.num_params += 2 * test_qubits
            test_qubits = int(np.ceil(test_qubits / 2))
        self.num_params -= 2
        self.params = 0.5 * np.random.randn(self.num_params, requires_grad=True)

    @staticmethod
    def pool(old_size: int) -> int:
        """
        Function that creates the pooling circuit of the QCNN. It reduces the number of qubits given to the function to its rounded-up half.

        Parameters:
        - old_size (int): The number of qubits currently active that need to be reduced by half.

        Returns:
        int: The new number of active qubits in the circuit.
        """
        new_size = int(np.ceil(old_size / 2))
        for i in range(new_size, old_size):
            qml.CNOT(wires=(i, old_size - i - 1))
        return new_size

    @staticmethod
    def convolution(num_qubits: int, params: NDArray[np.float_]) -> int:
        """
        Function that creates the convolution circuit of the QCNN as described in Slabbert's paper (see the references in the technical paper of the repository). It
        makes all of the qubits interact with each other with different weights of interaction (params). This function
        also works for a given amount of qubits. The interactions will go from the ith qubits to the
        (max(num_qubits - 3, 1)+i)%num_qubit qubit.

        Parameters:
        - num_qubits (int): The number of qubits currently active that need to interact together.
        - params (NDArray[np.float_]): The parameters that are yet to be used in the general circuit.

        Returns:
        int: The number of parameters used in this instance of the convolution circuit.
        """
        if num_qubits == 2:
            qml.RY(params[0], 0)
            qml.RY(params[1], 1)
            qml.CNOT((0, 1))
            return 2
        else:
            qubit_to_target = max(num_qubits - 3, 1)
            i_param = 0
            for i in range(num_qubits):
                target_qubit = (i + qubit_to_target) % (num_qubits)
                qml.RY(params[i_param], i)
                qml.RY(params[i_param + 1], target_qubit)
                qml.CNOT((i, target_qubit))
                i_param += 2
        return i_param

    def generate_qcnn_circuit(
        self, feature_vector: NDArray[np.float_], params: NDArray[np.float_]
    ) -> List[float]:
        """
        Method that creates the QCNN circuit to be used by the class.

        Parameters:
        - self: The QCNN_Solver object that will use this circuit.
        - feature_vector (NDArray[np.float_]): The feature vector to be encoded in the instance of the circuit.
        - params (NDArray[np.float_]): The parameters to be assigned to each parametrized gate of the convolution subcircuits.

        Returns:
        List[float]: The probabilities associated with each basis state in the circuit. They will not be directly accessible
                     since a QNode needs to be created with this function to work.
        """
        num_params_utilized = 0
        num_qubits_utilized = self.num_qubits
        self.embedding(feature_vector)
        while True:
            num_params_utilized += self.convolution(
                num_qubits_utilized, params[num_params_utilized:]
            )
            num_qubits_utilized = self.pool(num_qubits_utilized)
            if num_qubits_utilized == 1:
                break
        return qml.expval(qml.PauliZ(0))

    def run(
        self,
        feature_vectors: NDArray[np.float_],
        labels: NDArray[np.float_],
        optimizer_function: callable,
        error_function: callable = mean_square_error,
        training_ratio: float = 0.8,
    ) -> Tuple[int, NDArray[np.int_]]:
        """
        Method to run the variationnal quatum classifier algorithm. By using a training dataset, for a set of training vectors,
        it will predict their associated labels.

        Parameters:
        - self: The VQC_Solver object to call the method on.
        - feature_vectors (NDArray[np.float_]): The feature vectors used to train the classifier. The prediction vectors are also in this array. They are after the training ones.
        - labels: (NDArray[np.float_]): The labels associated with the feature vectors. The ones given for the prediction phase will be used
                                        to optimize the circuit. The labels must be in the same order as their associated feature vector in the feature_vectors matrix.
                                        The value of each label must be -1 or 1.
        - optimizer_function (callable): The function that optimizes the cost function with a given set of parameters. It must have only two parameters in this order:
                                         the cost function to optimize and the parameter array to be used. It returns the optimized parameters.
        - error_function (callable = mean_square_error): The function that takes for input the labels given by the classifier and their real value and gives a numeric value of exactness. This function is then optimized.
                                                         The optimizer will tweak the parameters to minimize the result of that function. The function must directly use the expectation values in the calculation. In
                                                         other words, it can not transform the prediction data to calculate the cost.
        - training_ratio (float = 0.8): The ratio of the number of feature vectors used for training over the total number of feature vectors.

        Returns:
        Tuple[int, NDArray[np.int_]]:  - The number of correctly predicted labels.
                                       - The prediction labels of the testing feature vectors.
        """
        training_period = int(training_ratio * len(labels))

        training_vectors = feature_vectors[:training_period, :]
        testing_vectors = feature_vectors[training_period:, :]
        training_labels = labels[:training_period]
        testing_labels = labels[training_period:]

        predictions = np.empty_like(testing_labels)

        # optimizing the ansatz
        def cost_function(
            params: NDArray[np.float_],
        ):
            resulting_labels = [
                self.circuit_to_optimize(training_vector, params)
                for training_vector in training_vectors
            ]
            return error_function(resulting_labels, training_labels)

        self.params = optimizer_function(cost_function, self.params)

        # Getting the predictions
        for i, testing_vector in enumerate(testing_vectors):
            predictions[i] = np.sign(
                self.circuit_to_optimize(testing_vector, self.params)
            )

        return get_score(predictions, testing_labels), predictions

    def run_batched(
        self,
        feature_vectors: NDArray[np.float_],
        labels: NDArray[np.float_],
        optimizer_function: callable,
        error_function: callable = mean_square_error,
        num_batches: int = 10,
        training_ratio: float = 0.8,
    ) -> Tuple[int, NDArray[np.int_]]:
        """
        Method to run the variationnal quatum classifier algorithm. By using a training dataset, for a set of training vectors,
        it will predict their associated labels. It will batch the training set into num_batches batches. So, the training vectors will only be used
        once to optimize the parameters.

        Parameters:
        - self: The VQC_Solver object to call the method on.
        - feature_vectors (NDArray[np.float_]): The feature vectors used to train the classifier. The prediction vectors are also in this array. They are after the training ones.
        - labels: (NDArray[np.float_]): The labels associated with the feature vectors. The ones given for the prediction phase will be used
                                        to optimize the circuit. The labels must be in the same order as their associated feature vector in the feature_vectors matrix.
                                        The value of each label must be -1 or 1.
        - optimizer_function (callable): The function that optimizes the cost function with a given set of parameters. It must have only two parameters in this order:
                                         the cost function to optimize and the parameter array to be used. It returns the optimized parameters.
        - error_function (callable = mean_square_error): The function that takes for input the labels given by the classifier and their real value and gives a numeric value of exactness. This function is then optimized.
                                                         The optimizer will tweak the parameters to minimize the result of that function. The function must directly use the expectation values in the calculation. In
                                                         other words, it can not transform the prediction data to calculate the cost.
        - num_batches (int = 10): The number of batches that the training period must be divided into.
        - training_ratio (float = 0.8): The ratio of the number of feature vectors used for training over the total number of feature vectors.

        Returns:
        Tuple[int, NDArray[np.int_]]:  - The number of correctly predicted labels.
                                       - The prediction labels of the testing feature vectors.
        """

        training_period = int(training_ratio * len(labels))

        training_vectors = feature_vectors[:training_period, :]
        testing_vectors = feature_vectors[training_period:, :]
        training_labels = labels[:training_period]
        testing_labels = labels[training_period:]

        predictions = np.empty_like(testing_labels)

        batch_lenght = int(len(training_labels) / num_batches)

        # Optimising the weights of the interactions
        batch_number = 0

        def cost_function(
            params,
        ):
            nonlocal batch_number
            batched_training_vectors = training_vectors[
                batch_number * batch_lenght : (batch_number + 1) * batch_lenght,
                :,
            ]
            batched_training_labels = training_labels[
                batch_number * batch_lenght : (batch_number + 1) * batch_lenght
            ]

            resulting_labels = [
                self.circuit_to_optimize(training_vector, params)
                for training_vector in batched_training_vectors
            ]

            batch_number = batch_number + 1
            return error_function(resulting_labels, batched_training_labels)

        self.params = optimizer_function(cost_function, self.params)

        # Getting the predictions
        for i, testing_vector in enumerate(testing_vectors):
            predictions[i] = np.sign(
                self.circuit_to_optimize(testing_vector, self.params)
            )

        return get_score(predictions, testing_labels), predictions
