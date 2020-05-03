from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from .sample.ddd import DddDataset
from .sample.exdet import EXDetDataset
from .sample.ctdet import CTDetDataset
from .sample.gaila_ctdet import GAILA_CTDetDataset
from .sample.multi_pose import MultiPoseDataset

from .dataset.gaila import GAILA
from .dataset.coco import COCO
from .dataset.pascal import PascalVOC
from .dataset.kitti import KITTI
from .dataset.coco_hp import COCOHP


dataset_factory = {
  'gaila': GAILA,
  'coco': COCO,
  'pascal': PascalVOC,
  'kitti': KITTI,
  'coco_hp': COCOHP
}

_sample_factory = {
  'gaila_ctdet': GAILA_CTDetDataset,
  'exdet': EXDetDataset,
  'ctdet': CTDetDataset,
  'ddd': DddDataset,
  'multi_pose': MultiPoseDataset
}


def get_dataset(dataset, task):
  class Dataset(dataset_factory[dataset], _sample_factory[task]):
    pass
  return Dataset
  
