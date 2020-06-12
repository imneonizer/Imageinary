import os
import re
import numpy
import click
import tensorflow as tf
import mxnet as mx
from PIL import Image
from multiprocessing.pool import Pool
from time import perf_counter
from math import ceil

@click.group()
def main():
    """
    CLI for generating a fake dataset of various quantities at different resolutions. Supports .jpg for now.
    """
    pass

@main.command()
@click.option('--path', required=True)
@click.option('--name', required=True)
@click.option('--width', default=1920, required=True)
@click.option('--height', default=1080, required=True)
@click.option('--count', default=1, required=True)
@click.option('--image_format', default='png', required=True)
@click.option('--seed', default=0)
@click.option('--size', is_flag=True, default=False)
def create_images(path, name, width, height, count, image_format, seed, size):
    click.echo("Creating {} {} files located at {} of {}x{} resolution with a base filename of {}".format(count, image_format, path, width, height, name))

    combined_path = os.path.join(path, name)

    #Expected to yield a thread pool equivalent to the number of CPU cores in the system
    with Pool() as pool:
        start_time = perf_counter()
        pool.starmap(image_creation, ((combined_path, width, height, seed, image_format, n) for n in range(count)))

    stop_time = perf_counter()

    if size:
        is_first_image = True
        first_image_size = 0
        directory_size = 0
        for image_name in os.listdir(path):
            if os.path.isdir(os.path.join(path, image_name)):
                continue
            image_path = os.path.join(path, image_name)
            directory_size += os.path.getsize(image_path)
            if is_first_image:
                first_image_size = directory_size
                is_first_image = False
        click.echo("First image size, in bytes: {}".format(first_image_size))
        click.echo("Directory size, in bytes: {}".format(directory_size))

    click.echo("Created {} files in {} seconds".format(count, stop_time-start_time))

@main.command()
@click.option('--source_path', required=True)
@click.option('--dest_path', required=True)
@click.option('--name', required=True)
@click.option('--img_per_file', default=1000)
def create_recordio(source_path, dest_path, name, img_per_file):
    print ("Creating RecordIO files at {} from {} targeting {} files per record with a base filename of {}".format(dest_path, source_path, img_per_file, name))
    image_files = []
    source_path = os.path.abspath(source_path)
    dest_path = os.path.abspath(dest_path)
    
    for image_name in os.listdir(source_path):
        if os.path.isdir(os.path.join(source_path, image_name)):
            continue
        else:
            image_files.append(image_name)
    
    num_of_records = ceil(len(image_files) / img_per_file)
    with Pool() as pool:
        start_time = perf_counter()
        pool.starmap(recordio_creation, ((source_path, dest_path, name, image_files[ n*img_per_file:(n*img_per_file) + img_per_file], n) for n in range(num_of_records)))

    stop_time = perf_counter()
    print("Completed in {} seconds".format(stop_time-start_time))

@main.command()
@click.option('--source_path', required=True)
@click.option('--dest_path', required=True)
@click.option('--name', required=True)
@click.option('--img_per_file', default=1000)
def create_tfrecords(source_path, dest_path, name, img_per_file):
    click.echo("Creating TFRecord files at {} from {} targeting {} files per TFRecord with a base filename of {}".format(dest_path, source_path, img_per_file, name))

    combined_path = os.path.join(dest_path, name)

    image_count = 0
    record = 0

    start_time = perf_counter()
    writer = tf.io.TFRecordWriter(combined_path + str(record))
    for image_name in os.listdir(source_path):
        if os.path.isdir(os.path.join(source_path, image_name)):
            continue
        image_count += 1
        if image_count > img_per_file:
            image_count = 1
            writer.close()
            record += 1
            writer = tf.io.TFRecordWriter(combined_path + str(record))
        image_path = os.path.join(source_path, image_name)
        image = open(image_path, "rb").read()

        feature = {
            'image/encoded': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image])),
            'image/class/label': tf.train.Feature(int64_list=tf.train.Int64List(value=[0]))
        }

        tfrecord_entry = tf.train.Example(features=tf.train.Features(feature=feature))
        writer.write(tfrecord_entry.SerializeToString())

    writer.close()
    stop_time = perf_counter()

    click.echo("Completed in {} seconds".format(stop_time-start_time))

def recordio_creation(source_path, dest_path, name, image_files, n):
    combined_path = os.path.join(dest_path, name)
    regex = re.compile('\d+')
    dataset_rec = combined_path + str(n) + '.rec'
    dataset_idx = combined_path + str(n) + '.idx'
    recordio_ds = mx.recordio.MXIndexedRecordIO(os.path.join(dest_path, dataset_idx),
                                               os.path.join(dest_path, dataset_rec), 'w')

    for image_name in image_files:
        image_path = os.path.join(source_path, image_name)
        image_index = int(regex.findall(image_name)[0])
        header = mx.recordio.IRHeader(0, 0, image_index, 0)
        image = open(image_path, "rb").read()
        packed_image = mx.recordio.pack(header, image)
        recordio_ds.write_idx(image_index, packed_image)

    recordio_ds.close()


def image_creation(combined_path, width, height, seed, image_format, n):
    supportedImageFormats = {"jpg":"jpg", "JPG":"jpg", "jpeg":"jpg", "JPEG":"jpg",\
                             "bmp":"bmp", "BMP":"bmp", "bitmap":"bmp", "BITMAP":"bmp",\
                             "png":"png", "PNG":"png"}
    numpy.random.seed(seed + n)
    fileExt = None
    a = numpy.random.rand(height,width,3) * 255
    if image_format in supportedImageFormats.keys():
        fileExt = supportedImageFormats[image_format]
    else:
        fileExt = "png"
    if fileExt == "jpg":
        im_out = Image.fromarray(a.astype('uint8')).convert('RGB')
    else:
        im_out = Image.fromarray(a.astype('uint8')).convert('RGBA')

    im_out.save('%s%d.%s' % (combined_path, n, fileExt))
    return

if __name__ == "__main__":
    main()
