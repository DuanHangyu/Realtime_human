import uuid
import tqdm
import numpy as np
import cv2
import sys
import os
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from talkingface.data.few_shot_dataset import get_image
import gzip
import math
import pickle
import mediapipe as mp
import shutil
from talkingface.utils import crop_mouth, main_keypoints_index, smooth_array
import json
from model.obj.wrap_utils import index_wrap, index_edge_wrap
import pickle

mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection

def detect_face(frame, min_detection_confidence = 0.5):
    # 剔除掉多个人脸、大角度侧脸（鼻子不在两个眼之间）、部分人脸框在画面外、人脸像素低于80*80的
    with mp_face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=min_detection_confidence) as face_detection:
        results = face_detection.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not results.detections or len(results.detections) > 1:
            return -1, None
        rect = results.detections[0].location_data.relative_bounding_box
        out_rect = [rect.xmin, rect.xmin + rect.width, rect.ymin, rect.ymin + rect.height]
        nose_ = mp_face_detection.get_key_point(
            results.detections[0], mp_face_detection.FaceKeyPoint.NOSE_TIP)
        l_eye_ = mp_face_detection.get_key_point(
            results.detections[0], mp_face_detection.FaceKeyPoint.LEFT_EYE)
        r_eye_ = mp_face_detection.get_key_point(
            results.detections[0], mp_face_detection.FaceKeyPoint.RIGHT_EYE)
        # print(nose_, l_eye_, r_eye_)
        if nose_.x > l_eye_.x or nose_.x < r_eye_.x:
            return -2, out_rect

        h, w = frame.shape[:2]
        # print(frame.shape)
        if out_rect[0] < 0 or out_rect[2] < 0 or out_rect[1] > w or out_rect[3] > h:
            return -3, out_rect
        if rect.width * w < 60 or rect.height * h < 60:
            return -4, out_rect
    return 1, out_rect


def calc_face_interact(face0, face1):
    x_min = min(face0[0], face1[0])
    x_max = max(face0[1], face1[1])
    y_min = min(face0[2], face1[2])
    y_max = max(face0[3], face1[3])
    tmp0 = ((face0[1] - face0[0]) * (face0[3] - face0[2])) / ((x_max - x_min) * (y_max - y_min))
    tmp1 = ((face1[1] - face1[0]) * (face1[3] - face1[2])) / ((x_max - x_min) * (y_max - y_min))
    return min(tmp0, tmp1)


def detect_face_mesh(frame):
    with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5) as face_mesh:
        results = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        pts_3d = np.zeros([478, 3])
        if not results.multi_face_landmarks:
            print("****** WARNING! No face detected! ******")
        else:
            image_height, image_width = frame.shape[:2]
            for face_landmarks in results.multi_face_landmarks:
                for index_, i in enumerate(face_landmarks.landmark):
                    x_px = min(math.floor(i.x * image_width), image_width - 1)
                    y_px = min(math.floor(i.y * image_height), image_height - 1)
                    z_px = min(math.floor(i.z * image_width), image_width - 1)
                    pts_3d[index_] = np.array([x_px, y_px, z_px])
        return pts_3d


def ExtractFromVideo(video_path, face_rect=None):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0

    dir_path = os.path.dirname(video_path)
    vid_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # 宽度
    vid_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # 高度

    totalFrames = cap.get(cv2.CAP_PROP_FRAME_COUNT)  # 总帧数
    totalFrames = int(totalFrames)
    pts_3d = np.zeros([totalFrames, 478, 3])
    face_rect_list = []

    # os.makedirs("../preparation/{}/image".format(model_name))
    for frame_index in tqdm.tqdm(range(totalFrames)):
        ret, frame = cap.read()  # 按帧读取视频
        # #到视频结尾时终止
        if ret is False:
            break

        if frame_index == 0:
            # 检测人脸
            tag_, rect = detect_face(frame, min_detection_confidence = 0.25)
            if tag_ != 1:
                tag_, rect = detect_face(frame[int(0.1 * vid_height):int(0.9 * vid_height),
                                         int(0.1 * vid_width):int(0.9 * vid_width)], min_detection_confidence=0.25)
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
            y_mid = (y_min + y_max) / 2.
            x_mid = (x_min + x_max) / 2.
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
        # print(y_min, y_max, x_min, x_max)
        # cv2.imshow("s", frame_face)
        # cv2.waitKey(10)
        frame_kps = detect_face_mesh(frame_face)
        pts_3d[frame_index] = frame_kps + np.array([x_min, y_min, 0])

        # point_size = 1
        # point_color = (0, 0, 255)  # BGR
        # thickness = 4  # 0 、4、8
        # for coor in pts_3d[frame_index]:
        #     # coor = (coor +1 )/2.
        #     cv2.circle(frame, (int(coor[0]), int(coor[1])), point_size, point_color, thickness)
        # cv2.imshow("a", frame)
        # cv2.waitKey(30)
    cap.release()  # 释放视频对象
    return pts_3d


def PrepareVideo(video_in_path, video_out_path, face_rect=[200, 200, 520, 520]):
    # 1 视频转换为25FPS
    subprocess.run(["ffmpeg", "-i", video_in_path, "-r", "25", "-an", "-loglevel", "quiet", "-y", video_out_path], check=False)

    cap = cv2.VideoCapture(video_out_path)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    print("视频帧数：", frames)
    pts_3d = ExtractFromVideo(video_out_path, face_rect)
    if type(pts_3d) is np.ndarray and len(pts_3d) == frames:
        print("关键点已提取")
    Path_output_pkl = video_out_path[:-4] + ".pkl"
    with open(Path_output_pkl, "wb") as f:
        pickle.dump(pts_3d, f)

def data_preparation_mini(video_mouthOpen, video_mouthClose, video_dir_path):
    new_data_path = os.path.join(video_dir_path, "data")
    os.makedirs(new_data_path, exist_ok=True)
    video_out_path = "{}/circle.mp4".format(new_data_path)
    # CirculateVideo(video_mouthClose, video_out_path, face_rect=[290, 190, 440, 350])
    PrepareVideo(video_mouthClose, video_out_path, face_rect=None)
    video_out_path = "{}/ref.mp4".format(new_data_path)
    PrepareVideo(video_mouthOpen, video_out_path, face_rect=None)
    
def step0_keypoints(video_path, out_path):
    Path_output_pkl = video_path + "/circle.pkl"
    with open(Path_output_pkl, "rb") as f:
        pts_3d = pickle.load(f)

    pts_3d = pts_3d.reshape(len(pts_3d), -1)
    smooth_array_ = smooth_array(pts_3d, weight=[0.03, 0.1, 0.74, 0.1, 0.03])
    pts_3d = smooth_array_.reshape(len(pts_3d), 478, 3)

    video_path = os.path.join(video_path, "circle.mp4")
    cap = cv2.VideoCapture(video_path)
    vid_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # 宽度
    vid_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # 高度
    cap.release()
    out_path = os.path.join(out_path, "01.mp4")
    try:
        # 复制文件
        shutil.copy(video_path, out_path)
        print(f"视频已成功复制到 {out_path}")
    except Exception as e:
        print(f"复制文件时出错: {e}")
    return pts_3d,vid_width,vid_height

def step1_crop_mouth(pts_3d, vid_width, vid_height):
    list_source_crop_rect = [crop_mouth(source_pts[main_keypoints_index], vid_width, vid_height) for source_pts in
                             pts_3d]
    list_source_crop_rect = np.array(list_source_crop_rect).reshape(len(pts_3d), -1)
    face_size = (list_source_crop_rect[:,2] - list_source_crop_rect[:,0]).mean()/2.0 + (list_source_crop_rect[:,3] - list_source_crop_rect[:,1]).mean()/2.0
    face_size = int(face_size)//2 * 2
    face_mid = (list_source_crop_rect[:,2:] + list_source_crop_rect[:,0:2])/2.
    # step 1: Smooth Cropping Rectangle Transition
    # Since HTML video playback can have inconsistent frame rates and may not align precisely from frame to frame, adjust the cropping rectangle to transition smoothly, compensating for potential misalignment.
    face_mid = smooth_array(face_mid, weight=[0.10, 0.20, 0.40, 0.20, 0.10])
    face_mid = face_mid.astype(int)
    if face_mid[:, 0].max() + face_size / 2 > vid_width or face_mid[:, 1].max() + face_size / 2 > vid_height:
        raise ValueError("人脸范围超出了视频，请保证视频合格后再重试")

    list_source_crop_rect = np.concatenate([face_mid - face_size // 2, face_mid + face_size // 2], axis = 1)

    # import pandas as pd
    # pd.DataFrame(list_source_crop_rect).to_csv("sss.csv")

    standard_size = 128
    list_standard_v = []
    for frame_index in range(len(list_source_crop_rect)):
        source_pts = pts_3d[frame_index]
        source_crop_rect = list_source_crop_rect[frame_index]
        print(source_crop_rect)
        standard_v = get_image(source_pts, source_crop_rect, input_type="mediapipe", resize=standard_size)

        list_standard_v.append(standard_v)

    return list_source_crop_rect, list_standard_v

def step2_generate_obj(list_source_crop_rect, list_standard_v, out_path):
    from model.obj.obj_utils import generateRenderInfo, generateWrapModel
    render_verts, render_face = generateRenderInfo()
    face_pts_mean = render_verts[:478, :3].copy()

    wrapModel_verts, wrapModel_face = generateWrapModel()
    # 求平均人脸
    from talkingface.run_utils import calc_face_mat
    mat_list, _, face_pts_mean_personal_primer = calc_face_mat(np.array(list_standard_v), face_pts_mean)

    from model.obj.utils import INDEX_MP_LIPS
    face_pts_mean_personal_primer[INDEX_MP_LIPS] = face_pts_mean[INDEX_MP_LIPS] * 0.5 + face_pts_mean_personal_primer[INDEX_MP_LIPS] * 0.5

    from model.obj.wrap_utils import newWrapModel
    face_wrap_entity = newWrapModel(wrapModel_verts, face_pts_mean_personal_primer)

    with open(os.path.join(out_path,"face3D.obj"), "w") as f:
        for i in face_wrap_entity:
            f.write("v {:.3f} {:.3f} {:.3f} {:.02f} {:.0f}\n".format(i[0], i[1], i[2], i[3], i[4]))
        for i in range(len(wrapModel_face) // 3):
            f.write("f {0} {1} {2}\n".format(wrapModel_face[3 * i] + 1, wrapModel_face[3 * i + 1] + 1,
                                             wrapModel_face[3 * i + 2] + 1))
    json_data = []
    for frame_index in range(len(list_source_crop_rect)):
        source_crop_rect = list_source_crop_rect[frame_index]
        standard_v = list_standard_v[frame_index]

        standard_v = standard_v[index_wrap, :2].flatten().tolist()
        mat = mat_list[frame_index].T.flatten().tolist()
        # 将 standard_v 中所有元素四舍五入到两位小数
        standard_v_rounded = [round(i, 5) for i in mat] + [round(i, 1) for i in standard_v]
        print(len(standard_v_rounded), 16 + 209 * 2)
        json_data.append({"rect": source_crop_rect.tolist(), "points": standard_v_rounded})
        # print(json_data)
        # break
    with open(os.path.join(out_path, "json_data.json"), "w") as f:
        json.dump(json_data, f)

def step3_generate_ref_tensor(video_path, out_path):
    from talkingface.render_model_mini import RenderModel_Mini
    renderModel_mini = RenderModel_Mini()
    renderModel_mini.loadModel("checkpoint/DINet_mini/epoch_40.pth")

    # 读取ref video信息
    Path_output_pkl = "{}/ref.pkl".format(video_path)
    with open(Path_output_pkl, "rb") as f:
        ref_images_info = pickle.load(f)

    video_path = "{}/ref.mp4".format(video_path)
    cap = cv2.VideoCapture(video_path)
    vid_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_width_ref = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_height_ref = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    list_standard_img_ref = []
    list_standard_v_ref = []
    standard_size = 128
    for frame_index in range(min(vid_frame_count, len(ref_images_info))):
        ret, frame = cap.read()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        source_pts = ref_images_info[frame_index]
        source_crop_rect = crop_mouth(source_pts[main_keypoints_index], vid_width_ref, vid_height_ref)

        standard_img = get_image(frame, source_crop_rect, input_type="image", resize=standard_size)
        standard_v = get_image(source_pts, source_crop_rect, input_type="mediapipe", resize=standard_size)
        list_standard_img_ref.append(standard_img)
        list_standard_v_ref.append(standard_v)
    cap.release()

    renderModel_mini.reset_charactor(list_standard_img_ref, np.array(list_standard_v_ref)[:, main_keypoints_index], standard_size = standard_size)

    ref_in_feature = renderModel_mini.net.infer_model.ref_in_feature
    ref_in_feature = ref_in_feature.detach().squeeze(0).cpu().float().numpy().flatten()
    # print(1111, ref_in_feature.shape)

    np.savetxt(os.path.join(out_path, 'ref_data.txt'), ref_in_feature, fmt='%.8f')

def generate_combined_data(list_source_crop_rect, list_standard_v, video_path, out_path):
    from model.obj.obj_utils import generateRenderInfo, generateWrapModel
    from talkingface.run_utils import calc_face_mat
    from model.obj.utils import INDEX_MP_LIPS
    from model.obj.wrap_utils import newWrapModel
    from talkingface.render_model_mini import RenderModel_Mini

    # Step 2: Generate face3D.obj data
    render_verts, render_face = generateRenderInfo()
    face_pts_mean = render_verts[:478, :3].copy()

    wrapModel_verts, wrapModel_face = generateWrapModel()
    mat_list, _, face_pts_mean_personal_primer = calc_face_mat(np.array(list_standard_v), face_pts_mean)

    face_pts_mean_personal_primer[INDEX_MP_LIPS] = face_pts_mean[INDEX_MP_LIPS] * 0.5 + face_pts_mean_personal_primer[INDEX_MP_LIPS] * 0.5

    face_wrap_entity = newWrapModel(wrapModel_verts, face_pts_mean_personal_primer)

    face3D_data = []
    for i in face_wrap_entity:
        face3D_data.append("v {:.3f} {:.3f} {:.3f} {:.02f} {:.0f}\n".format(i[0], i[1], i[2], i[3], i[4]))
    for i in range(len(wrapModel_face) // 3):
        face3D_data.append("f {0} {1} {2}\n".format(wrapModel_face[3 * i] + 1, wrapModel_face[3 * i + 1] + 1,
                                                   wrapModel_face[3 * i + 2] + 1))

    # Step 3: Generate ref_data.txt data
    renderModel_mini = RenderModel_Mini()
    renderModel_mini.loadModel("checkpoint/DINet_mini/epoch_40.pth")

    Path_output_pkl = "{}/ref.pkl".format(video_path)
    with open(Path_output_pkl, "rb") as f:
        ref_images_info = pickle.load(f)

    video_path = "{}/ref.mp4".format(video_path)
    cap = cv2.VideoCapture(video_path)
    vid_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_width_ref = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_height_ref = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    list_standard_img_ref = []
    list_standard_v_ref = []
    standard_size = 128
    for frame_index in range(min(vid_frame_count, len(ref_images_info))):
        ret, frame = cap.read()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        source_pts = ref_images_info[frame_index]
        source_crop_rect = crop_mouth(source_pts[main_keypoints_index], vid_width_ref, vid_height_ref)

        standard_img = get_image(frame, source_crop_rect, input_type="image", resize=standard_size)
        standard_v = get_image(source_pts, source_crop_rect, input_type="mediapipe", resize=standard_size)
        list_standard_img_ref.append(standard_img)
        list_standard_v_ref.append(standard_v)
    cap.release()

    renderModel_mini.reset_charactor(list_standard_img_ref, np.array(list_standard_v_ref)[:, main_keypoints_index], standard_size=standard_size)

    ref_in_feature = renderModel_mini.net.infer_model.ref_in_feature
    ref_in_feature = ref_in_feature.detach().squeeze(0).cpu().float().numpy().flatten()

    # 保留两位小数
    rounded_array = np.round(ref_in_feature, 6)

    # Combine all data into a single JSON object
    combined_data = {
        "uid": "matesx_" + str(uuid.uuid4()),
        "frame_num": len(list_standard_v),
        "face3D_obj": face3D_data,
        "ref_data": rounded_array.tolist(),
        "json_data": [],
        "authorized": False,
    }

    for frame_index in range(len(list_source_crop_rect)):
        source_crop_rect = list_source_crop_rect[frame_index]
        standard_v = list_standard_v[frame_index]

        standard_v = standard_v[index_wrap, :2].flatten().tolist()
        mat = mat_list[frame_index].T.flatten().tolist()
        standard_v_rounded = [round(i, 5) for i in mat] + [round(i, 1) for i in standard_v]
        combined_data["json_data"].append({"rect": source_crop_rect.tolist(), "points": standard_v_rounded})
 
    output_file = os.path.join(out_path, "data")
    with gzip.open(output_file, 'wt', encoding='UTF-8') as f:
        json.dump(combined_data, f)

def data_preparation_web(path):
    video_path = os.path.join(path, "data")
    out_path = os.path.join(path, "assets")
    os.makedirs(out_path, exist_ok=True)
    pts_3d, vid_width,vid_height = step0_keypoints(video_path, out_path)
    list_source_crop_rect, list_standard_v = step1_crop_mouth(pts_3d, vid_width, vid_height)
    # step2_generate_obj(list_source_crop_rect, list_standard_v, out_path)
    # step3_generate_ref_tensor(video_path, out_path)
    generate_combined_data(list_source_crop_rect, list_standard_v, video_path, out_path)






def main():
    # 检查命令行参数的数量
    if len(sys.argv) != 3:
        print("Usage: python data_preparation_mini.py 视频 <输出文件夹位置>")
        sys.exit(1)  # 参数数量不正确时退出程序

    # 获取video_name参数
    video_mouthOpen = sys.argv[1]
    video_dir_path = sys.argv[2]
    print(f"Video dir path is set to: {video_dir_path}")
    data_preparation_mini(video_mouthOpen, video_mouthOpen, video_dir_path)
    data_preparation_web(video_dir_path)
    print("训练完成，文件在"+video_dir_path+"assets 里面")

if __name__ == "__main__":
    main()
    # python video_data_disponse.py kkn.mp4 test