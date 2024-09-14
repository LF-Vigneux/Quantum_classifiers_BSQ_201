import numpy as np
from numpy.typing import NDArray
from kernel_method import Quantum_Kernel_Classification
from vqc_method import get_vqc_result
import quantum_embeddings
from utils import get_feature_vectors_and_labels

from pennylane.templates import RandomLayers  # QCNN

# Package à télécharger... Tout les optimiseurs sans gradients de Powell
import pdfo

from scipy.optimize import minimize, OptimizeResult, Bounds

# À voir si SPSA ou PSO utile, utiliser optimizer.py de mon stage cet été.


def main(
    feature_vectors: NDArray[np.float_], labels: NDArray[np.int_], training_ratio: int
):

    num_qubits = 4

    # To use the kernel_angle_embedding function correctly, you need to use a wrapper functions with the number of qubits and the rotation gate to use
    rotation = "Y"

    def angle_embedding(a):
        return quantum_embeddings.angle_embedding(
            a, num_qubits=num_qubits, rotation=rotation
        )

    """
    The class is then called, the number of qubits need to be coherent with the embedding:
    angle_embedding: no qubits restrictions
    amplitude_embedding: qubits muste be the base two log of the input. This number must be rounded up to the next integer
    iqp_embedding: The number of qubits must be the same as the number of features
    """
    kernel_qml = Quantum_Kernel_Classification(angle_embedding, num_qubits)
    # kernel_qml=Quantum_Kernel_Classification(quantum_embeddings.amplitude_embedding,num_qubits)
    # kernel_qml=Quantum_Kernel_Classification(quantum_embeddings.iqp_embedding,num_qubits)

    score, predictions = kernel_qml.run(
        feature_vectors, labels, training_ratio=training_ratio
    )

    training_period = int(len(labels) * 0.8)

    print("The score of the kernel: ", score)
    print("The predictions of the labels: ", predictions)
    print("The true value of the labels: ", labels[training_period:])


if __name__ == "__main__":
    feature_vectors, labels = get_feature_vectors_and_labels(
        "HTRU_2", extension="csv", path="datasets/", rows_to_skip=0
    )

    # Réduire dataset, trop gros:
    feature_vectors = feature_vectors[1949:2049, :]
    labels = labels[1949:2049]

    training_ratio = 0.8
    main(feature_vectors, labels, training_ratio)
