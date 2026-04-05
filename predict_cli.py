import argparse
import json
import os

import numpy as np
import tensorflow as tf
from PIL import Image

from config import CLASS_NAMES, IMG_SIZE, MODEL_PATH, TRAINING_SUMMARY_PATH
from sensor_utils import compare_levels, sensor_distance_to_level


def load_class_names():
    if os.path.exists(TRAINING_SUMMARY_PATH):
        with open(TRAINING_SUMMARY_PATH, 'r', encoding='utf-8') as handle:
            summary = json.load(handle)
        names = summary.get('class_names')
        if isinstance(names, list) and names:
            return [str(name).strip().lower() for name in names]
    return CLASS_NAMES[:]


def preprocess_image(image_path):
    image = Image.open(image_path).convert('RGB').resize(IMG_SIZE)
    array = np.asarray(image, dtype=np.float32)
    return np.expand_dims(array, axis=0)


def main():
    parser = argparse.ArgumentParser(description='Predict dustbin waste level from an image.')
    parser.add_argument('--image', required=True, help='Path to the image file')
    parser.add_argument('--sensor-distance', type=float, default=None, help='Optional ultrasonic distance in cm')
    args = parser.parse_args()

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f'Model not found at {MODEL_PATH}. Train the model first.')

    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    class_names = load_class_names()
    prediction = model.predict(preprocess_image(args.image), verbose=0)[0]
    predicted_index = int(np.argmax(prediction))
    ai_level = class_names[predicted_index]

    print(f'Predicted AI level: {ai_level}')
    print(f'Confidence: {prediction[predicted_index] * 100:.2f}%')
    print('Class probabilities:')
    for index, class_name in enumerate(class_names):
        print(f'  {class_name}: {prediction[index] * 100:.2f}%')

    if args.sensor_distance is not None:
        sensor_level = sensor_distance_to_level(args.sensor_distance)
        print(f'Ultrasonic sensor distance: {args.sensor_distance:.2f} cm')
        print(f'Ultrasonic sensor level: {sensor_level}')
        print(f'Comparison result: {compare_levels(ai_level, sensor_level)}')


if __name__ == '__main__':
    main()
