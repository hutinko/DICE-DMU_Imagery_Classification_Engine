import os, sys, io, datetime, urllib

import tensorflow as tf
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

sys.path.append("inception_files")

from datasets import imagenet
from nets.inception_v1 import inception_v1, inception_v1_arg_scope, inception_v1_base
from preprocessing import inception_preprocessing

slim            = tf.contrib.slim

IMAGE_SIZE      = inception_v1.default_image_size

MODEL_REPO_URL  = "https://raw.githubusercontent.com/DEKHTIARJonathan/DICE-DMU_Imagery_Classification_Engine/web-api"

MODELDIR_PATH      = os.path.join("inception_files", "models")

MODEL_NAME      = "dice_dmunet.ckpt"
MODEL_FILEPATH  = os.path.join(MODELDIR_PATH, MODEL_NAME)
MODEL_URL       = os.path.join(MODEL_REPO_URL, MODELDIR_PATH, MODEL_NAME)

LABEL_FILE_NAME = "dmunet_labels.txt"
LABEL_FILE_PATH  = os.path.join(MODELDIR_PATH, LABEL_FILE_NAME)

JPEG_EXT_LIST   = ["jpg", "jpeg"]

class Tensorflow_ImagePredictor():

    sess              = None

    ext_plh           = tf.placeholder(tf.string)
    img_plh           = tf.placeholder(tf.string, shape=None)

    names             = None

    def __init__(self):
        print("Tensorflow_ImagePredictor: Model Checking Starting ...")

        if not os.path.isdir(MODELDIR_PATH):
            os.makedirs(MODELDIR_PATH)

        if not os.path.isfile(MODEL_FILEPATH):
            urllib.request.urlretrieve (MODEL_URL, MODEL_FILEPATH)

        if not os.path.isfile(LABEL_FILE_PATH):
            self.names = imagenet.create_readable_names_for_imagenet_labels()
        else:
            labels = open(LABEL_FILE_PATH, 'r')

            #Create a dictionary to refer each label to their string name
            self.names = {}
            for line in labels:
                label, string_name = line.split(':')
                string_name = string_name[:-1] #Remove newline
                self.names[int(label)] = string_name

        print("Tensorflow_ImagePredictor: Model Checking Finished ...\n")
        
        ########################################################################

        print("Tensorflow_ImagePredictor: Initialisation Starting ...")

        self.file_cond         = tf.equal(self.ext_plh, JPEG_EXT_LIST)
        self.file_cond         = tf.count_nonzero(self.file_cond)
        self.file_cond         = tf.equal(self.file_cond, 1) ## 1 => JPEG EXTENSION, 0 => PNG EXTENSION

        self.image             = tf.cond(
                                     self.file_cond,
                                     lambda: tf.image.decode_jpeg(self.img_plh, channels=3),
                                     lambda: tf.image.decode_png(self.img_plh, channels=3)
                                )

        self.processed_image   = inception_preprocessing.preprocess_image(self.image, IMAGE_SIZE, IMAGE_SIZE, is_training=False)
        self.processed_images  = tf.expand_dims(self.processed_image, 0)
        
        
        #Config is necessary in order to prevent windows GPU compute failure
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        self.sess = tf.Session(config=config)

        # Create the model, use the default arg scope to configure the batch norm parameters.
        with slim.arg_scope(inception_v1_arg_scope()):
            self.logits, self._ = inception_v1(self.processed_images, num_classes=len(self.names), is_training=False)
        
        self.probabilities = tf.nn.softmax(self.logits)

        self.init_fn           = slim.assign_from_checkpoint_fn(
                                    MODEL_FILEPATH,
                                    slim.get_variables_to_restore()
                                 )
        
        self.init_fn(self.sess)

        print("Tensorflow_ImagePredictor: Initialisation Finished ...")

    def predict(self, image, image_ext):

        np_image, probabilities =self. sess.run([self.image, self.probabilities], feed_dict={self.img_plh: image, self.ext_plh: image_ext})
        probabilities = probabilities[0, 0:]
        sorted_inds = [i[0] for i in sorted(enumerate(-probabilities), key=lambda x:x[1])]

        payload = dict()
        payload["success"] = True
        payload["timestamp"] = str(datetime.datetime.now())

        payload["results"] = list()

        for i in range(5):
            tmp = dict()

            index = sorted_inds[i]

            tmp["position"]    = i + 1 # First position is Number 0 so we need to add 1!
            tmp["probability"] = 100*probabilities[index]
            tmp["class_name"]  = self.names[index]

            payload["results"].append(tmp)

        return payload
