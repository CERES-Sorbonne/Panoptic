import os
import sys

import concurrent
import itertools
from operator import itemgetter

# import cv2
import numpy as np
import pandas as pd
import pytesseract
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from PIL import Image

os.environ['TESSDATA_PREFIX'] = os.getenv('TESSDATA_PREFIX', os.sep.join([*sys.executable.split(os.sep)[:-1], 'share', 'tessdata']))

tess_config = "-c tessedit_char_blacklist='+=*;)(][\{\}@/|_^\\#~&'"

#
# def full_ocr(image: Image):
#     img = np.array(image)
#
#     # create list of combinations (preprocessing + language) to try
#     operations = list(itertools.product([_no_preprocess, _bilateral], ['eng', 'fra']))
#
#     # run in parallel
#     # TODO: passer en multiprocess plutôt que threaded ?
#     with ThreadPoolExecutor(max_workers=4) as executor:
#         futures = [executor.submit(_preprocess_and_ocr, img, o[0], o[1]) for o in operations]
#         return max([f.result() for f in concurrent.futures.as_completed(futures)], key=itemgetter(1))
#
#
# def _no_preprocess(img):
#     return img


# def _bilateral(img):
#     img = cv2.bilateralFilter(img, 5, 55, 60)
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     _, img = cv2.threshold(img, 240, 255, 1)
#     return img
#
#
# def _adaptive(img):
#     imgf = cv2.adaptiveThreshold(img, 200, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 2)
#     return imgf
#
#
# def _normalize(img):
#     # normalize image
#     norm_img = np.zeros((img.shape[0], img.shape[1]))
#     return cv2.normalize(img, norm_img, 0, 255, cv2.NORM_MINMAX)
#
#
# def _remove_noise(img):
#     print(img.shape)
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 15)


def _image_to_blocks(img, lang="fra", config="--oem 3 --psm 1 " + tess_config):
    d = pytesseract.image_to_data(img, lang=lang, config=config, output_type='data.frame')
    # on filtre les données où la confiance est nulle ou négative
    d = d[d.conf > 0]
    # on filtre les données où le texte ne vaut rien
    if d.empty:
        return d
    try:
        d.text = d.text.str.strip()
    except Exception as e:
        raise e
    d.replace('', np.nan, inplace=True)
    d.dropna(inplace=True)

    if d.empty:
        return d
    # on regroupe par blocs
    lines = d.groupby(['block_num', 'par_num', 'line_num'])['text'].apply(list)
    # on calcule la confiance par bloc
    conf = d.groupby(['block_num', 'par_num', 'line_num'])['conf'].mean()
    # on calcule les coordonnées de bloc
    x1 = d.groupby(['block_num', 'par_num', 'line_num'])['left'].min()
    y1 = d.groupby(['block_num', 'par_num', 'line_num'])['top'].min()
    x2 = d.groupby(['block_num', 'par_num', 'line_num'])['left'].max() + \
         d.groupby(['block_num', 'par_num', 'line_num'])['width'].max()
    y2 = y1 + d.groupby(['block_num', 'par_num', 'line_num'])['height'].max()
    # on stocke le tout dans un nouveau dataframe
    output_df = pd.DataFrame({'text': lines, 'confidence': conf, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
    return output_df


def _preprocess_and_ocr(img, preprocess, lang):
    img = preprocess(img)
    return _make_ocr(img, lang)


def _make_ocr(img, lang='eng'):
    final_text = ""
    final_confidence = 0

    df = _image_to_blocks(img, lang=lang)
    if df.empty:
        return "", 0
    for index, row in df.iterrows():
        actual_text = ' '.join(row['text']).strip('').replace('\n', '')
        if row['confidence'] < 90:
            new_image = img[row['y1']:row['y2'], row['x1']:row['x2']]
            new_row = _image_to_blocks(new_image, lang=lang, config="--oem 3 --psm 6" + tess_config)
            if new_row.empty:
                final_text += actual_text
                continue
            new_row = new_row.iloc[0]
            new_text = ' '.join(new_row['text']).strip('').replace('\n', '')
            new_confidence = new_row['confidence']
            if new_confidence > row['confidence']:
                final_text += " " + new_text + " "
            else:
                final_text += actual_text
            final_confidence += max(new_confidence, row['confidence'])
        else:
            final_text += actual_text
            final_confidence += row['confidence']
    final_confidence = final_confidence / df.shape[0]
    return final_text.strip(), final_confidence