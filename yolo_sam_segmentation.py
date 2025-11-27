from pathlib import Path
import cv2
import numpy as np
from ultralytics import SAM, YOLO
import os
import glob
from datetime import datetime


SOURCE_DIR = Path("received_images")
YOLO_MODEL_PATH = "model/yolov8n.pt"
SAM_MODEL_PATH = "model/sam2.1_b.pt"
PERSON_CLASS_NAME = "person"
YOLO_CONFIDENCE = 0.2
DEVICE = "cpu"
FILL_COLOR = (255, 0, 0)
MASK_ALPHA = 0.6


# ===========================
# YOLO: 人物検出
# ===========================
def detect_person_boxes(model: YOLO, image: np.ndarray, class_id: int) -> list[list[float]]:
    results = model(image, save=False, verbose=False, conf=YOLO_CONFIDENCE)
    person_boxes = []

    for result in results:
        if result.boxes is None or result.boxes.xyxy is None:
            continue

        cls_tensor = result.boxes.cls
        if cls_tensor is None:
            continue

        mask = cls_tensor.int() == class_id
        if mask.any():
            boxes = result.boxes.xyxy[mask].cpu().tolist()
            person_boxes.extend(boxes)

    return person_boxes


# ===========================
# SAM: セグメンテーション
# ===========================
def segment_with_sam(model: SAM, image: np.ndarray, boxes):
    return model(
        image,
        bboxes=boxes,
        save=False,
        verbose=False,
        device=DEVICE,
    )


# ===========================
# YOLO枠描画
# ===========================
def draw_yolo_boxes(image: np.ndarray, yolo_results, class_id: int) -> np.ndarray:
    for result in yolo_results:
        if result.boxes is None or result.boxes.xyxy is None:
            continue

        for box, cls, conf in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.cls.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
        ):
            if int(cls) == class_id:
                x1, y1, x2, y2 = box.astype(int)
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

    return image


# ===========================
# マスク適用
# ===========================
def apply_masks(image: np.ndarray, sam_result, color, alpha):
    if sam_result.masks is None or sam_result.masks.data is None:
        return image

    blended = image.astype(np.float32)
    mask_color = np.array(color, dtype=np.float32)

    for mask in sam_result.masks.data:
        mask_array = mask.cpu().numpy().astype(bool)
        blended[mask_array] = blended[mask_array] * (1.0 - alpha) + mask_color * alpha

    return blended.astype(np.uint8)


# ===========================
# 動画生成
# ===========================
def process_images_to_masked_video():
    # 1. 入力画像の収集
    image_paths = sorted(
        glob.glob(str(SOURCE_DIR / "*.png")),
        key=lambda x: int(os.path.splitext(os.path.basename(x))[0])
    )

    if not image_paths:
        raise FileNotFoundError("received_images 内に PNG が見つかりません。")

    # 2. YOLO & SAM 読み込み
    yolo_model = YOLO(YOLO_MODEL_PATH)
    sam_model = SAM(SAM_MODEL_PATH)

    person_class_id = 0  # YOLO の person クラス

    # 3. 動画出力先
    os.makedirs("movies", exist_ok=True)

    idx = 1
    while True:
        output_path = f"movies/output_{idx}.mp4"
        if not os.path.exists(output_path):
            break
        idx += 1

    # 4. 動画設定（H.264）
    first_frame = cv2.imread(image_paths[0])
    height, width, _ = first_frame.shape

    fourcc = cv2.VideoWriter_fourcc(*'H264')
    fps = 5
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # 5. 各フレームを処理
    for path in image_paths:
        frame = cv2.imread(path)

        # YOLO
        yolo_results = yolo_model(frame, save=False, verbose=False, conf=YOLO_CONFIDENCE)
        person_boxes = detect_person_boxes(yolo_model, frame, person_class_id)

        if person_boxes:
            sam_results = segment_with_sam(sam_model, frame, person_boxes)
            sam_result = sam_results[0]
            masked_image = apply_masks(frame, sam_result, FILL_COLOR, MASK_ALPHA)
        else:
            masked_image = frame

        # YOLO 枠を重ねる
        final_frame = draw_yolo_boxes(masked_image, yolo_results, person_class_id)

        # 動画へ追加
        video.write(final_frame)
        print(f"Added frame to video: {path}")

    video.release()
    print(f"動画作成完了: {output_path}")
    return output_path


if __name__ == "__main__":
    process_images_to_masked_video()
