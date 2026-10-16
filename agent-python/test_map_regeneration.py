"""Explicit regenerate must not replay a completed final-map checkpoint."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class RegenerationTests(unittest.TestCase):
 def test_direct_explicit_request_always_runs_final_synthesis(self):
  from direct_course_map import build_saved_direct_map
  with tempfile.TemporaryDirectory() as d, patch('direct_course_map.build_direct_course_map',return_value={'status':'completed'}) as build:
   build_saved_direct_map([],[],[],keyframe_dir=Path(d))
   self.assertIsNone(build.call_args.kwargs.get('checkpoint'))
 def test_grouped_explicit_request_does_not_cache_final_synthesis(self):
  from grouped_analysis import build_saved_group_map
  pages=[{'pageIndex':1,'groupUnderstanding':{'status':'completed'}}]
  with tempfile.TemporaryDirectory() as d, patch('course_mind_map.build_course_mind_map',return_value={'status':'completed'}) as build:
   build_saved_group_map([],pages,[],keyframe_dir=Path(d))
   self.assertIsNone(build.call_args.kwargs.get('checkpoint'))
