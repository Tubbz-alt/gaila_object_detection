from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pycocotools.coco as coco
from pycocotools.cocoeval import COCOeval
import numpy as np
import json
import os
import random
import glob
from tqdm import tqdm
import re
import pandas as pd

import torch.utils.data as data


class GAILA(data.Dataset):
    num_classes = None #80
    default_resolution = None #[512, 512]
    mean = None #np.array([0.40789654, 0.44719302, 0.47026115], dtype=np.float32).reshape(1, 1, 3)
    std = None #np.array([0.28863828, 0.27408164, 0.27809835], dtype=np.float32).reshape(1, 1, 3)

    def __init__(self, opt, split):

        super(GAILA, self).__init__()

        ########## KEPT TEMPORARILY ##############
        self.data_dir = os.path.join(opt.data_dir, 'coco')
        self.img_dir = os.path.join(self.data_dir, '{}2017'.format(split))
        if split == 'test':
            self.annot_path = os.path.join(
                self.data_dir, 'annotations',
                'image_info_test-dev2017.json').format(split)
        else:
            if opt.task == 'exdet':
                self.annot_path = os.path.join(
                    self.data_dir, 'annotations',
                    'instances_extreme_{}2017.json').format(split)
            else:
                self.annot_path = os.path.join(
                    self.data_dir, 'annotations',
                    'instances_{}2017.json').format(split)
        self.max_objs = 128
        self.class_name = ['__background__', 'nothing']
        self._valid_ids = [0]
        self.cat_ids = {v: i for i, v in enumerate(self._valid_ids)}
        self.voc_color = [(v // 32 * 64 + 64, (v // 8) % 4 * 64, v % 8 * 32) \
                          for v in range(1, self.num_classes + 1)]
        self._data_rng = np.random.RandomState(123)
        self._eig_val = np.array([0.2141788, 0.01817699, 0.00341571],
                                 dtype=np.float32)
        self._eig_vec = np.array([
            [-0.58752847, -0.69563484, 0.41340352],
            [-0.5832747, 0.00994535, -0.81221408],
            [-0.56089297, 0.71832671, 0.41158938]
        ], dtype=np.float32)
        # self.mean = np.array([0.485, 0.456, 0.406], np.float32).reshape(1, 1, 3)
        # self.std = np.array([0.229, 0.224, 0.225], np.float32).reshape(1, 1, 3)
        ########## KEPT TEMPORARILY ##############

        self.split = split  # which split of the dataset we are looking at
        self.opt = opt

        task_dirs = glob.glob(os.path.join(opt.frames_dir, '*/*'))  # list of all task directories

        if self.split != 'train':
            selected_dirs = list(filter(lambda x: re.search(r'_1c_task[123]|_2c_task[456]', x), task_dirs))
        else:
            selected_dirs = list(filter(lambda x: not re.search(r'_1c_task[123]|_2c_task[456]', x), task_dirs))

        self.all_frames = []  # (frame path, frame dataframe containing annotations)
        for _dir in tqdm(selected_dirs, desc=f'Loading {split} annotation files'):
            image_ids = os.listdir(_dir)
            image_ids = [int(img.split('.')[0]) for img in image_ids]  # list of image IDs
            bbox_path = os.path.join(opt.bounds_dir, os.path.basename(_dir) + '_bounds.txt')
            with open(bbox_path, 'r') as f:
                lines = f.readlines()
                bbox_frame = pd.DataFrame([json.loads(line.rstrip()) for line in lines[
                                                                                 :-1]])  # GEO: this will include a faulty frame (missing 1 object). Please exclude the whole frame
            bbox_frame = bbox_frame[bbox_frame['step'].isin(image_ids)]
            bbox_frame = list(bbox_frame.groupby('step'))  # list of step/frame groups
            random.shuffle(bbox_frame)
            selected_frames = bbox_frame[:opt.frames_per_task]
            selected_frames = [(os.path.join(_dir, str(i) + '.png'), j) for i, j in selected_frames]
            self.all_frames.extend(selected_frames)

        random.shuffle(self.all_frames)

        for i in range(len(opt.bounds_dir)):  # find common path part
            if opt.frames_dir[i] != opt.bounds_dir[i]:
                break
        gaila_dir = opt.bounds_dir[:i]
        # GEO: no, this file contains crap too. Read the classes from all unique objects in the 'name' column of the dataframe. Exclude 'Wall'
        class_names = [line.rstrip() for line in open(os.path.join(os.path.join(gaila_dir, 'possible_labels.txt'))).readlines()]

        self.cat_ids = {name: ind for ind, name in enumerate(class_names)}

        self.num_samples = len(self.all_frames)

        print('Loaded {} samples for {}'.format(self.num_samples, split))

    def _to_float(self, x):
        return float("{:.2f}".format(x))

    def convert_eval_format(self, all_bboxes):
        # import pdb; pdb.set_trace()
        detections = []
        for image_id in all_bboxes:
            for cls_ind in all_bboxes[image_id]:
                category_id = self._valid_ids[cls_ind - 1]
                for bbox in all_bboxes[image_id][cls_ind]:
                    bbox[2] -= bbox[0]
                    bbox[3] -= bbox[1]
                    score = bbox[4]
                    bbox_out = list(map(self._to_float, bbox[0:4]))

                    detection = {
                        "image_id": int(image_id),
                        "category_id": int(category_id),
                        "bbox": bbox_out,
                        "score": float("{:.2f}".format(score))
                    }
                    if len(bbox) > 5:
                        extreme_points = list(map(self._to_float, bbox[5:13]))
                        detection["extreme_points"] = extreme_points
                    detections.append(detection)
        return detections

    def __len__(self):
        return self.num_samples

    def save_results(self, results, save_dir):
        json.dump(self.convert_eval_format(results),
                  open('{}/results.json'.format(save_dir), 'w'))

    def run_eval(self, results, save_dir):
        # result_json = os.path.join(save_dir, "results.json")
        # detections  = self.convert_eval_format(results)
        # json.dump(detections, open(result_json, "w"))
        self.save_results(results, save_dir)
        coco_dets = self.coco.loadRes('{}/results.json'.format(save_dir))
        coco_eval = COCOeval(self.coco, coco_dets, "bbox")
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()
