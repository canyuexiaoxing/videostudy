import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from slide_grouping import group_pages


def block(text):
    return {"text": text, "score": 0.98, "polygon": [[10, 10], [100, 10], [100, 35], [10, 35]]}


def frame(time_ms, *texts):
    return {"frameTimeMs": time_ms, "ocrBlocks": [block(text) for text in texts]}


class SlideGroupingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def image(self, time_ms, color=255, mark=0):
        canvas = np.full((180, 320, 3), color, np.uint8)
        if mark:
            cv2.rectangle(canvas, (40, 45), (120, 85), (mark, mark, mark), -1)
        cv2.imwrite(str(self.root / f"{time_ms}.jpg"), canvas)

    def test_progressive_reveal_merges_and_preserves_time_sources(self):
        self.image(28000, mark=20)
        self.image(56000, mark=20)
        pages, transitions = group_pages([
            frame(28000, "例题一：增长量", "现期192，基期160"),
            frame(56000, "例题一：增长量", "现期192，基期160", "192-160=32"),
        ], self.root, [], ask_json=lambda _: self.fail("clear reveal must not call model"))
        self.assertEqual(transitions, [])
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["memberFrameTimesMs"], [28000, 56000])
        self.assertEqual(pages[0]["representativeFrameTimesMs"], [56000])
        self.assertTrue(any(line["text"] == "192-160=32" and line["sourceFrameTimeMs"] == 56000
                            for line in pages[0]["ocrLines"]))

    def test_same_template_new_problem_is_not_merged(self):
        self.image(28000, mark=20)
        self.image(56000, mark=20)
        pages, _ = group_pages([
            frame(28000, "例题一：苹果产量", "2025年产量100吨"),
            frame(56000, "例题二：小麦价格", "2026年价格200元"),
        ], self.root, [], ask_json=lambda _: self.fail("replacement is clear"))
        self.assertEqual([page["memberFrameTimesMs"] for page in pages], [[28000], [56000]])

    def test_blank_transition_does_not_create_page(self):
        self.image(1000, mark=20)
        self.image(2000)
        self.image(3000, mark=40)
        pages, transitions = group_pages([
            frame(1000, "上一页的主要文字"), frame(2000), frame(3000, "下一页的不同内容"),
        ], self.root, [], ask_json=lambda _: {"samePage": False})
        self.assertEqual(transitions, [2000])
        self.assertEqual(len(pages), 2)

    def test_revisited_same_slide_after_blank_is_a_new_temporal_page(self):
        self.image(1000, mark=20)
        self.image(2000)
        self.image(3000, mark=20)
        pages, transitions = group_pages([
            frame(1000, "同一张课件标题"), frame(2000), frame(3000, "同一张课件标题"),
        ], self.root, [], ask_json=lambda _: self.fail("blank transition must split first"))
        self.assertEqual(transitions, [2000])
        self.assertEqual([page["memberFrameTimesMs"] for page in pages], [[1000], [3000]])

    def test_sparse_diagram_uses_image_change_and_keeps_later_representation(self):
        self.image(1000, mark=20)
        self.image(2000, mark=20)
        pages, _ = group_pages([frame(1000), frame(2000)], self.root, [],
                                 ask_json=lambda _: self.fail("identical diagrams must not call model"))
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["representativeFrameTimesMs"], [2000])

    def test_small_capture_shift_does_not_split_a_diagram_page(self):
        first = np.full((180, 320, 3), 255, np.uint8)
        cv2.rectangle(first, (55, 30), (230, 125), (20, 20, 20), 3)
        cv2.line(first, (70, 110), (210, 45), (40, 40, 40), 3)
        cv2.imwrite(str(self.root / "1000.jpg"), first)
        shifted = cv2.warpAffine(first, np.float32([[1, 0, 3], [0, 1, 2]]), (320, 180),
                                 borderValue=(255, 255, 255))
        cv2.imwrite(str(self.root / "2000.jpg"), shifted)
        pages, _ = group_pages([frame(1000), frame(2000)], self.root, [],
                                 ask_json=lambda _: self.fail("small shift should be aligned locally"))
        self.assertEqual(len(pages), 1)

    def test_uncertain_boundary_uses_only_text_and_respects_model_decision(self):
        self.image(1000, mark=20)
        self.image(2000, mark=50)
        payloads = []
        def decide(payload):
            payloads.append(payload)
            return {"samePage": True, "reason": "continued explanation"}
        pages, _ = group_pages([frame(1000, "图表"), frame(2000, "走势")], self.root,
                                 [{"startMs": 1000, "endMs": 2000, "text": "接着看走势"}], ask_json=decide)
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(payloads), 1)
        self.assertNotIn("image", str(payloads).lower())


if __name__ == "__main__":
    unittest.main()
