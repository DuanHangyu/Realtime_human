"""
Training pipeline extracted from video_data_disponse.py.
Each step reports progress via a callback for real-time UI updates.
"""

import uuid
import math
import os
import json
import gzip
import pickle
import shutil
import subprocess

import cv2
import numpy as np
import mediapipe as mp

from talkingface.data.few_shot_dataset import get_image
from talkingface.utils import crop_mouth, main_keypoints_index, smooth_array
from model.obj.wrap_utils import index_wrap

mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection

# Total number of steps in the pipeline
TOTAL_STEPS = 6

STEP_NAMES = [
    "视频预处理 (25fps转换 + 人脸关键点提取)",
    "关键点平滑",
    "嘴部裁剪矩形计算",
    "3D人脸模型生成",
    "参考特征提取 (DINet_mini)",
    "打包输出 (gzip JSON)",
]


class TrainingPipeline:
    """Wraps the full training flow with per-step progress reporting."""

    def __init__(self, video_path: str, output_dir: str):
        self.video_path = video_path
        self.output_dir = output_dir
        self.progress_callback = None  # Callable(step, step_name, percent, message)

    def _report(self, step: int, name: str, percent: float, msg: str = ""):
        if self.progress_callback:
            self.progress_callback(step, name, percent, msg)

    # ------------------------------------------------------------------
    # Face detection helpers (from video_data_disponse.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_face(frame, min_detection_confidence=0.5):
        with mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=min_detection_confidence,
        ) as face_detection:
            results = face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if not results.detections or len(results.detections) > 1:
                return -1, None
            rect = results.detections[0].location_data.relative_bounding_box
            out_rect = [rect.xmin, rect.xmin + rect.width, rect.ymin, rect.ymin + rect.height]
            nose_ = mp_face_detection.get_key_point(
                results.detections[0], mp_face_detection.FaceKeyPoint.NOSE_TIP
            )
            l_eye_ = mp_face_detection.get_key_point(
                results.detections[0], mp_face_detection.FaceKeyPoint.LEFT_EYE
            )
            r_eye_ = mp_face_detection.get_key_point(
                results.detections[0], mp_face_detection.FaceKeyPoint.RIGHT_EYE
            )
            if nose_.x > l_eye_.x or nose_.x < r_eye_.x:
                return -2, out_rect
            h, w = frame.shape[:2]
            if out_rect[0] < 0 or out_rect[2] < 0 or out_rect[1] > w or out_rect[3] > h:
                return -3, out_rect
            if rect.width * w < 60 or rect.height * h < 60:
                return -4, out_rect
        return 1, out_rect

    @staticmethod
    def _detect_face_mesh(frame):
        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as face_mesh:
            results = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            pts_3d = np.zeros([478, 3])
            if not results.multi_face_landmarks:
                print("WARNING: No face detected in frame!")
            else:
                image_height, image_width = frame.shape[:2]
                for face_landmarks in results.multi_face_landmarks:
                    for index_, i in enumerate(face_landmarks.landmark):
                        x_px = min(math.floor(i.x * image_width), image_width - 1)
                        y_px = min(math.floor(i.y * image_height), image_height - 1)
                        z_px = min(math.floor(i.z * image_width), image_width - 1)
                        pts_3d[index_] = np.array([x_px, y_px, z_px])
            return pts_3d

    def _extract_from_video(self, video_path, face_rect=None):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        vid_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        vid_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        pts_3d = np.zeros([total_frames, 478, 3])
        actual_frames = 0

        for frame_index in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            actual_frames += 1

            if frame_index == 0:
                tag_, rect = self._detect_face(frame, min_detection_confidence=0.25)
                if tag_ != 1:
                    tag_, rect = self._detect_face(
                        frame[
                            int(0.1 * vid_height) : int(0.9 * vid_height),
                            int(0.1 * vid_width) : int(0.9 * vid_width),
                        ],
                        min_detection_confidence=0.25,
                    )
                    assert tag_ == 1, "第一帧检测不到人脸"
                    x_min = int(rect[0] * vid_width + 0.1 * vid_width)
                    y_min = int(rect[2] * vid_height + 0.1 * vid_height)
                    x_max = int(rect[1] * vid_width + 0.1 * vid_width)
                    y_max = int(rect[3] * vid_height + 0.1 * vid_height)
                else:
                    x_min = int(rect[0] * vid_width)
                    y_min = int(rect[2] * vid_height)
                    x_max = int(rect[1] * vid_width)
                    y_max = int(rect[3] * vid_height)
                y_mid = (y_min + y_max) / 2.0
                x_mid = (x_min + x_max) / 2.0
                len_ = max(x_max - x_min, y_max - y_min)
                face_rect = [x_mid - len_, y_mid - len_, x_mid + len_, y_mid + len_]

            x_min, y_min, x_max, y_max = face_rect
            seq_w, seq_h = x_max - x_min, y_max - y_min
            x_mid, y_mid = (x_min + x_max) / 2, (y_min + y_max) / 2
            crop_size = int(max(seq_w * 1.35, seq_h * 1.35))
            x_min = int(max(0, x_mid - crop_size * 0.5))
            y_min = int(max(0, y_mid - crop_size * 0.45))
            x_max = int(min(vid_width, x_min + crop_size))
            y_max = int(min(vid_height, y_min + crop_size))

            frame_face = frame[y_min:y_max, x_min:x_max]
            frame_kps = self._detect_face_mesh(frame_face)
            pts_3d[frame_index] = frame_kps + np.array([x_min, y_min, 0])

            # Report sub-progress (within step 0)
            pct = int((frame_index + 1) / total_frames * 100)
            self._report(0, STEP_NAMES[0], pct, f"提取关键点 {frame_index + 1}/{total_frames}")

        cap.release()
        if actual_frames == 0:
            raise RuntimeError(f"无法从视频中读取任何帧: {video_path}")
        if actual_frames < total_frames:
            pts_3d = pts_3d[:actual_frames]
        return pts_3d

    def _prepare_video(self, video_in_path, video_out_path):
        """Convert video to 25fps and extract face keypoints."""
        subprocess.run(
            ["ffmpeg", "-i", video_in_path, "-r", "25", "-an", "-loglevel", "quiet", "-y", video_out_path],
            check=True,
        )

        cap = cv2.VideoCapture(video_out_path)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        pts_3d = self._extract_from_video(video_out_path)
        return pts_3d, int(frames)

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _step0_prepare_video(self):
        """Convert to 25fps + extract face keypoints for circle and ref videos."""
        self._report(0, STEP_NAMES[0], 0, "开始处理视频...")

        data_dir = os.path.join(self.output_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        # Process circle video (mouth closed)
        circle_out = os.path.join(data_dir, "circle.mp4")
        self._report(0, STEP_NAMES[0], 5, "转换 circle 视频 25fps...")
        pts_circle, frames_circle = self._prepare_video(self.video_path, circle_out)
        if pts_circle is None:
            raise RuntimeError("circle 视频处理失败")
        pkl_path = circle_out[:-4] + ".pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump(pts_circle, f)

        # Process ref video (same input for mouth open/close)
        ref_out = os.path.join(data_dir, "ref.mp4")
        self._report(0, STEP_NAMES[0], 55, "转换 ref 视频 25fps...")
        pts_ref, frames_ref = self._prepare_video(self.video_path, ref_out)
        if pts_ref is None:
            raise RuntimeError("ref 视频处理失败")
        pkl_path = ref_out[:-4] + ".pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump(pts_ref, f)

        self._report(0, STEP_NAMES[0], 100, "视频预处理完成")

    def _step1_smooth_keypoints(self):
        """Smooth keypoints and copy video."""
        self._report(1, STEP_NAMES[1], 0, "开始关键点平滑...")

        data_dir = os.path.join(self.output_dir, "data")
        pkl_path = os.path.join(data_dir, "circle.pkl")

        with open(pkl_path, "rb") as f:
            pts_3d = pickle.load(f)

        self._report(1, STEP_NAMES[1], 30, "执行平滑滤波...")
        pts_3d = pts_3d.reshape(len(pts_3d), -1)
        smooth_array_ = smooth_array(pts_3d, weight=[0.03, 0.1, 0.74, 0.1, 0.03])
        pts_3d = smooth_array_.reshape(len(smooth_array_), 478, 3)

        # Save smoothed keypoints back
        with open(pkl_path, "wb") as f:
            pickle.dump(pts_3d, f)

        # Copy video to assets folder
        src_video = os.path.join(data_dir, "circle.mp4")
        assets_dir = os.path.join(self.output_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        out_video = os.path.join(assets_dir, "01.mp4")
        shutil.copy(src_video, out_video)

        # Read video dimensions
        cap = cv2.VideoCapture(src_video)
        vid_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        vid_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()

        self._report(1, STEP_NAMES[1], 100, "关键点平滑完成")
        return pts_3d, vid_width, vid_height

    def _step2_crop_mouth(self, pts_3d, vid_width, vid_height):
        """Compute mouth crop rectangles."""
        self._report(2, STEP_NAMES[2], 0, "开始嘴部裁剪计算...")
        total_frames = len(pts_3d)

        self._report(2, STEP_NAMES[2], 10, "计算裁剪矩形...")
        list_source_crop_rect = [
            crop_mouth(source_pts[main_keypoints_index], vid_width, vid_height)
            for source_pts in pts_3d
        ]
        list_source_crop_rect = np.array(list_source_crop_rect).reshape(len(pts_3d), -1)

        face_size = (
            (list_source_crop_rect[:, 2] - list_source_crop_rect[:, 0]).mean() / 2.0
            + (list_source_crop_rect[:, 3] - list_source_crop_rect[:, 1]).mean() / 2.0
        )
        face_size = int(face_size) // 2 * 2
        face_mid = (list_source_crop_rect[:, 2:] + list_source_crop_rect[:, 0:2]) / 2.0

        self._report(2, STEP_NAMES[2], 30, "平滑裁剪矩形...")
        face_mid = smooth_array(face_mid, weight=[0.10, 0.20, 0.40, 0.20, 0.10])
        face_mid = face_mid.astype(int)

        if (
            face_mid[:, 0].max() + face_size / 2 > vid_width
            or face_mid[:, 1].max() + face_size / 2 > vid_height
        ):
            raise ValueError("人脸范围超出了视频，请保证视频合格后再重试")

        list_source_crop_rect = np.concatenate(
            [face_mid - face_size // 2, face_mid + face_size // 2], axis=1
        )

        standard_size = 128
        list_standard_v = []
        for frame_index in range(len(list_source_crop_rect)):
            source_pts = pts_3d[frame_index]
            source_crop_rect = list_source_crop_rect[frame_index]
            standard_v = get_image(
                source_pts, source_crop_rect, input_type="mediapipe", resize=standard_size
            )
            list_standard_v.append(standard_v)

            pct = int(40 + (frame_index + 1) / total_frames * 60)
            self._report(
                2,
                STEP_NAMES[2],
                pct,
                f"生成标准视图 {frame_index + 1}/{total_frames}",
            )

        self._report(2, STEP_NAMES[2], 100, "嘴部裁剪计算完成")
        return list_source_crop_rect, list_standard_v

    def _step3_generate_3d_face(self, list_source_crop_rect, list_standard_v):
        """Generate 3D face model and per-frame transform data."""
        self._report(3, STEP_NAMES[3], 0, "开始生成3D人脸模型...")

        from model.obj.obj_utils import generateRenderInfo, generateWrapModel
        from talkingface.run_utils import calc_face_mat
        from model.obj.utils import INDEX_MP_LIPS
        from model.obj.wrap_utils import newWrapModel

        self._report(3, STEP_NAMES[3], 10, "生成渲染信息...")
        render_verts, render_face = generateRenderInfo()
        face_pts_mean = render_verts[:478, :3].copy()

        wrapModel_verts, wrapModel_face = generateWrapModel()

        self._report(3, STEP_NAMES[3], 30, "计算人脸变换矩阵...")
        mat_list, _, face_pts_mean_personal_primer = calc_face_mat(
            np.array(list_standard_v), face_pts_mean
        )

        face_pts_mean_personal_primer[INDEX_MP_LIPS] = (
            face_pts_mean[INDEX_MP_LIPS] * 0.5
            + face_pts_mean_personal_primer[INDEX_MP_LIPS] * 0.5
        )

        self._report(3, STEP_NAMES[3], 50, "生成wrap模型...")
        face_wrap_entity = newWrapModel(wrapModel_verts, face_pts_mean_personal_primer)

        # Build face3D data lines
        face3D_data = []
        for i in face_wrap_entity:
            face3D_data.append(
                "v {:.3f} {:.3f} {:.3f} {:.02f} {:.0f}\n".format(i[0], i[1], i[2], i[3], i[4])
            )
        for i in range(len(wrapModel_face) // 3):
            face3D_data.append(
                "f {0} {1} {2}\n".format(
                    wrapModel_face[3 * i] + 1,
                    wrapModel_face[3 * i + 1] + 1,
                    wrapModel_face[3 * i + 2] + 1,
                )
            )

        # Build per-frame json_data
        self._report(3, STEP_NAMES[3], 70, "生成帧数据...")
        json_data = []
        total_frames = len(list_source_crop_rect)
        for frame_index in range(total_frames):
            source_crop_rect = list_source_crop_rect[frame_index]
            standard_v = list_standard_v[frame_index]
            standard_v = standard_v[index_wrap, :2].flatten().tolist()
            mat = mat_list[frame_index].T.flatten().tolist()
            standard_v_rounded = [round(i, 5) for i in mat] + [round(i, 1) for i in standard_v]
            json_data.append({"rect": source_crop_rect.tolist(), "points": standard_v_rounded})

            pct = int(70 + (frame_index + 1) / total_frames * 30)
            self._report(3, STEP_NAMES[3], pct, f"处理帧 {frame_index + 1}/{total_frames}")

        self._report(3, STEP_NAMES[3], 100, "3D人脸模型生成完成")
        return face3D_data, json_data, mat_list

    def _step4_generate_ref_data(self):
        """Extract DINet_mini reference features."""
        self._report(4, STEP_NAMES[4], 0, "加载 DINet_mini 模型...")

        from talkingface.render_model_mini import RenderModel_Mini

        renderModel_mini = RenderModel_Mini()
        self._report(4, STEP_NAMES[4], 20, "加载模型权重...")
        renderModel_mini.loadModel("checkpoint/DINet_mini/epoch_40.pth")

        data_dir = os.path.join(self.output_dir, "data")
        pkl_path = os.path.join(data_dir, "ref.pkl")

        with open(pkl_path, "rb") as f:
            ref_images_info = pickle.load(f)

        video_path = os.path.join(data_dir, "ref.mp4")
        cap = cv2.VideoCapture(video_path)
        vid_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        vid_width_ref = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vid_height_ref = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        list_standard_img_ref = []
        list_standard_v_ref = []
        standard_size = 128
        frame_count = min(vid_frame_count, len(ref_images_info))

        self._report(4, STEP_NAMES[4], 40, f"处理 ref 帧 0/{frame_count}...")
        for frame_index in range(frame_count):
            ret, frame = cap.read()
            if not ret:
                raise RuntimeError(f"无法读取 ref 视频第 {frame_index} 帧")
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            source_pts = ref_images_info[frame_index]
            source_crop_rect = crop_mouth(
                source_pts[main_keypoints_index], vid_width_ref, vid_height_ref
            )
            standard_img = get_image(
                frame, source_crop_rect, input_type="image", resize=standard_size
            )
            standard_v = get_image(
                source_pts, source_crop_rect, input_type="mediapipe", resize=standard_size
            )
            list_standard_img_ref.append(standard_img)
            list_standard_v_ref.append(standard_v)

            pct = int(40 + (frame_index + 1) / frame_count * 40)
            self._report(
                4,
                STEP_NAMES[4],
                pct,
                f"处理 ref 帧 {frame_index + 1}/{frame_count}",
            )

        cap.release()

        self._report(4, STEP_NAMES[4], 85, "生成参考特征...")
        renderModel_mini.reset_charactor(
            list_standard_img_ref,
            np.array(list_standard_v_ref)[:, main_keypoints_index],
            standard_size=standard_size,
        )

        ref_in_feature = renderModel_mini.net.infer_model.ref_in_feature
        ref_in_feature = ref_in_feature.detach().squeeze(0).cpu().float().numpy().flatten()
        rounded_array = np.round(ref_in_feature, 6)

        self._report(4, STEP_NAMES[4], 100, "参考特征提取完成")
        return rounded_array

    def _step5_package_output(self, face3D_data, json_data, ref_data, frame_num):
        """Package all data into a single gzip JSON file."""
        self._report(5, STEP_NAMES[5], 0, "打包输出数据...")

        assets_dir = os.path.join(self.output_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        combined_data = {
            "uid": "matesx_" + str(uuid.uuid4()),
            "frame_num": frame_num,
            "face3D_obj": face3D_data,
            "ref_data": ref_data.tolist(),
            "json_data": json_data,
            "authorized": False,
        }

        self._report(5, STEP_NAMES[5], 50, "写入 gzip 文件...")
        output_file = os.path.join(assets_dir, "data")
        with gzip.open(output_file, "wt", encoding="UTF-8") as f:
            json.dump(combined_data, f)

        self._report(5, STEP_NAMES[5], 100, "打包完成")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self):
        """Execute all 6 steps sequentially."""
        self._step0_prepare_video()

        pts_3d, vid_width, vid_height = self._step1_smooth_keypoints()

        list_source_crop_rect, list_standard_v = self._step2_crop_mouth(
            pts_3d, vid_width, vid_height
        )

        face3D_data, json_data, mat_list = self._step3_generate_3d_face(
            list_source_crop_rect, list_standard_v
        )

        ref_data = self._step4_generate_ref_data()

        self._step5_package_output(face3D_data, json_data, ref_data, len(list_standard_v))
