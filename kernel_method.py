"""
File containing the class of the quantum kernel method. The class of this classifier and its method are all in this file.
The function that runs the main algorithm is the .run method.
"""

import numpy as np
import pennylane as qml
from sklearn.svm import SVC
from numpy.typing import NDArray
from typing import Tuple, List
from utils.utils import get_qnode_instance


class Quantum_Kernel_Classification:
    def __init__(self, embedding_circuit: callable, num_qubits: int) -> None:
        """
        Object that can run the quantum kernel classification algorithm

        Parameters:
        - embedding_circuit (callable): The Python function describing the embedding circuit of the data. It must use the Pennylane architecture to create the circuit.
        - num_qubits (int): The number of qubits of the embedding circuit.

        Returns:
        None
        """
        self.embedding = embedding_circuit
        self.num_qubits = num_qubits
        self.kernel_circuit = get_qnode_instance(
            self.get_kernel_embedding, self.num_qubits
        )

    def get_kernel_embedding(
        self, a: NDArray[np.float_], b: NDArray[np.float_]
    ) -> List[float]:
        """
        Method that creates the complete kernel circuit to be used in the classifier.

        Parameters:
        - self: The Quantum_Kernel_Classification object that will use this circuit.
        - a (NDArray[np.float_]): The first feature vector to be passed to the circuit.
        - b (NDArray[np.float_]): The second feature vector to be passed to the circuit.

        Returns:
        List[float]: The probabilities associated with each basis state in the circuit. They will not be directly accessible
                     since a QNode needs to be created with this function to access them.
        """
        self.embedding(a)
        qml.adjoint(self.embedding)(b)
        return qml.probs(wires=range(self.num_qubits))

    def run(
        self,
        feature_vectors: NDArray[np.float_],
        labels: NDArray[np.float_],
        training_ratio: float = 0.8,
        svm=SVC,
    ) -> Tuple[int, NDArray[np.int_]]:
        """
        Method to run the quantum kernel classifier algorithm. By using a training dataset, for a set of training vectors,
        it will predict their associated labels.

        Parameters:
        - self: The Quantum_Kernel_Classification object to call the method on.
        - feature_vectors (NDArray[np.float_]): The feature vectors used to train the classifier. The prediction vectors are also in this array. They are after the training ones.
        - labels: (NDArray[np.float_]): The labels associated with the feature vectors. The ones given for the prediction phase will be used
                                        to determine the precision of the classifier. The labels must be in the same order as their associated feature vector in the feature_vectors matrix.
        - training_ratio (float = 0.8): The ratio of the number of feature vectors used for training over the total number of feature vectors.
        - svm=SVC: The support vector machine that the classifier will use. By default, the SVC from sklearn.svm is used.

        Returns:
        Tuple[int, NDArray[np.int_]]:  - The number of correctly predicted labels.
                                         - The prediction labels of the testing feature vectors.
        """

        def qkernel(A, B):
            return np.array([[self.kernel_circuit(a, b)[0] for b in B] for a in A])

        training_period = int(training_ratio * len(labels))

        training_vectors = feature_vectors[:training_period, :]
        testing_vecors = feature_vectors[training_period:, :]
        training_labels = labels[:training_period]
        testing_labels = labels[training_period:]

        model = svm(kernel=qkernel)
        model.fit(training_vectors, training_labels)

        score = model.score(testing_vecors, testing_labels)
        predictions = model.predict(testing_vecors)

        return score, predictions
