import argparse
import json
import os

import numpy as np
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from config import CLASS_NAMES, IMG_SIZE, MODEL_PATH


DEFAULT_TEST_DIR = os.path.join('Dataset', 'FINAL_3_LEVEL_DATASET', 'test')


def load_test_dataset(test_dir: str, batch_size: int):
    return tf.keras.utils.image_dataset_from_directory(
        test_dir,
        labels='inferred',
        label_mode='int',
        class_names=CLASS_NAMES,
        image_size=IMG_SIZE,
        batch_size=batch_size,
        shuffle=False,
    )


def evaluate_model(test_dir: str, batch_size: int):
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f'Model not found at {MODEL_PATH}. Train the model first.')
    if not os.path.isdir(test_dir):
        raise FileNotFoundError(f'Test dataset folder not found at {test_dir}.')

    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    model.compile(
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'],
    )
    dataset = load_test_dataset(test_dir, batch_size)

    loss, keras_accuracy = model.evaluate(dataset, verbose=0)
    probabilities = model.predict(dataset, verbose=0)
    predicted_indices = np.argmax(probabilities, axis=1)
    true_indices = np.concatenate([labels.numpy() for _, labels in dataset], axis=0)

    sklearn_accuracy = accuracy_score(true_indices, predicted_indices)
    report = classification_report(
        true_indices,
        predicted_indices,
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(true_indices, predicted_indices)

    return {
        'test_dir': os.path.abspath(test_dir),
        'model_path': MODEL_PATH,
        'loss': float(loss),
        'keras_accuracy': float(keras_accuracy),
        'accuracy': float(sklearn_accuracy),
        'num_samples': int(len(true_indices)),
        'class_names': CLASS_NAMES,
        'confusion_matrix': matrix.tolist(),
        'classification_report': report,
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate the saved waste-level model on the test dataset.')
    parser.add_argument(
        '--test-dir',
        default=DEFAULT_TEST_DIR,
        help='Path to the test dataset folder',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Batch size for evaluation',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Print raw JSON output instead of a formatted summary',
    )
    args = parser.parse_args()

    results = evaluate_model(args.test_dir, args.batch_size)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print('Model evaluation complete')
    print(f"Model: {results['model_path']}")
    print(f"Test set: {results['test_dir']}")
    print(f"Samples: {results['num_samples']}")
    print(f"Loss: {results['loss']:.4f}")
    print(f"Keras accuracy: {results['keras_accuracy'] * 100:.2f}%")
    print(f"Accuracy: {results['accuracy'] * 100:.2f}%")
    print('Confusion matrix:')
    for row in results['confusion_matrix']:
        print(f'  {row}')

    print('Per-class metrics:')
    for class_name in CLASS_NAMES:
        metrics = results['classification_report'][class_name]
        print(
            f"  {class_name}: precision={metrics['precision'] * 100:.2f}% "
            f"recall={metrics['recall'] * 100:.2f}% "
            f"f1={metrics['f1-score'] * 100:.2f}% "
            f"support={int(metrics['support'])}"
        )


if __name__ == '__main__':
    main()
