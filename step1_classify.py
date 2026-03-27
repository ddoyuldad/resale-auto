"""
STEP 1 — 이미지 분석 & 제품별 폴더 분류
  - AI 모드: Gemini Vision API로 자동 분류 + 제품 정보 추출
  - 수동 모드: 사용자가 직접 이미지 확인 후 분류
  - 기존 폴더 모드: 이미 분류된 폴더에서 AI로 제품 정보 추출
"""
import os, sys, json, shutil, base64, glob
from pathlib import Path
from PIL import Image, ImageOps

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


def get_image_files(folder):
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    files = []
    for f in sorted(os.listdir(folder)):
        if Path(f).suffix.lower() in exts:
            files.append(os.path.join(folder, f))
    return files


def load_image_for_gemini(path, max_size=800):
    """Gemini용 PIL 이미지 로드 (리사이즈)"""
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    return img


def _parse_json_response(text):
    """AI 응답에서 JSON 파싱"""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if part.startswith("json"):
                text = part[4:].strip()
                break
            elif "{" in part:
                text = part.strip()
                break
    return json.loads(text)


# ─── AI로 제품 정보 추출 (기존 폴더용) ──────────────────────────
def analyze_product_with_ai(image_files, folder_name, api_key):
    """
    이미 분류된 폴더의 이미지를 Gemini AI로 분석해서 상세 제품 정보를 추출
    대표 이미지 2~3장만 분석 (비용 절약)
    """
    if not HAS_GENAI:
        print("   ⚠️  google-genai 패키지 미설치. pip install google-genai")
        return None

    client = genai.Client(api_key=api_key)

    # 대표 이미지 선택 (첫 장, 1/3 지점, 2/3 지점)
    sample_indices = [0]
    if len(image_files) >= 3:
        sample_indices.append(len(image_files) // 3)
        sample_indices.append(len(image_files) * 2 // 3)
    elif len(image_files) >= 2:
        sample_indices.append(len(image_files) - 1)

    contents = []
    for idx in sample_indices:
        if idx < len(image_files):
            contents.append(f"[이미지 {idx+1}: {os.path.basename(image_files[idx])}]")
            contents.append(load_image_for_gemini(image_files[idx]))

    contents.append(f"""위 이미지들은 "{folder_name}" 폴더의 같은 제품 사진입니다. (총 {len(image_files)}장)

이 제품을 최대한 상세히 분석해서 아래 JSON으로 응답해 주세요 (다른 텍스트 없이):
{{
    "product_name": "정확한 제품명",
    "brand": "브랜드/제조사명",
    "category": "카테고리 (건강기능식품/생활용품/식품/헤어케어/뷰티 등)",
    "spec": "규격/용량 (예: 400mg × 30정, 14g × 40ea 등)",
    "price_tag": "이미지에 보이는 가격 (예: 2,900원). 없으면 빈 문자열",
    "feature": "제품 핵심 특징 요약 (성분, 효능, 특이사항 등 | 로 구분)",
    "manufacturer": "제조사 (브랜드와 다를 경우)",
    "origin": "원산지 (보이는 경우, 예: 대한민국)",
    "ingredients": "주요 성분 (보이는 경우)",
    "usage": "용법/용량 (보이는 경우)",
    "certification": "인증 정보 (건강기능식품 인증, KC인증 등)",
    "barcode": "바코드 번호 (보이는 경우)",
    "expiry_info": "유통기한 정보 (보이는 경우)",
    "package_type": "포장 형태 (박스, 파우치, 병, 튜브 등)",
    "target_audience": "타겟 소비자 (예: 성인, 남성, 여성, 어린이 등)",
    "selling_point": "핵심 셀링포인트 (마케팅 문구 등)"
}}

이미지에서 확인할 수 없는 항목은 빈 문자열("")로 입력하세요.
가격표, 스티커, 라벨에 적힌 정보를 최대한 읽어 주세요.""")

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
        )
        return _parse_json_response(resp.text)
    except Exception as e:
        print(f"   ⚠️  AI 분석 오류: {e}")
        return None


# ─── AI 자동 분류 (루트 이미지들) ──────────────────────────────
def classify_with_ai(image_files, api_key):
    if not HAS_GENAI:
        print("⚠️  google-genai 패키지 미설치. pip install google-genai")
        return {}

    client = genai.Client(api_key=api_key)

    print(f"\n📸 총 {len(image_files)}장의 이미지를 Gemini AI로 분석합니다...")
    print("   (이미지 수에 따라 1~5분 소요될 수 있습니다)\n")

    batch_size = 5
    all_results = {}

    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i+batch_size]
        print(f"   분석 중... [{i+1}~{min(i+batch_size, len(image_files))}] / {len(image_files)}")

        contents = []
        for idx, fpath in enumerate(batch):
            contents.append(f"[이미지 {idx+1}: {os.path.basename(fpath)}]")
            contents.append(load_image_for_gemini(fpath))

        contents.append("""위 이미지들을 분석해서 각 이미지가 어떤 제품인지 분류해 주세요.

반드시 아래 JSON 형식으로만 응답해 주세요 (다른 텍스트 없이):
{
  "파일명1.jpg": {
    "product_name": "제품명",
    "brand": "브랜드/제조사",
    "category": "카테고리 (건강기능식품/생활용품/식품 등)",
    "spec": "규격/용량 (확인 가능한 경우)",
    "price_tag": "가격표 금액 (이미지에 보이면)",
    "feature": "제품 특징 요약",
    "folder_name": "폴더명 (제품명_브랜드 형태, 한글+영문 가능)",
    "manufacturer": "제조사",
    "origin": "원산지",
    "ingredients": "주요 성분",
    "usage": "용법/용량",
    "certification": "인증 정보",
    "barcode": "바코드 번호",
    "expiry_info": "유통기한",
    "package_type": "포장 형태",
    "target_audience": "타겟 소비자",
    "selling_point": "핵심 셀링포인트"
  },
  ...
}

주의사항:
- 같은 제품의 다른 각도 사진은 같은 folder_name으로 통일
- folder_name은 파일시스템에 안전한 이름으로 (특수문자 제외)
- 가격표가 보이면 price_tag에 금액만 기재 (예: "2,900원")
- 확인 불가한 항목은 빈 문자열("") 입력""")

        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
            )
            parsed = _parse_json_response(resp.text)
            for fname, info in parsed.items():
                matched = [f for f in batch if os.path.basename(f) == fname]
                if matched:
                    all_results[matched[0]] = info
                else:
                    idx_match = list(parsed.keys()).index(fname)
                    if idx_match < len(batch):
                        all_results[batch[idx_match]] = info
        except json.JSONDecodeError:
            print(f"   ⚠️  AI 응답 파싱 실패, 이 배치는 수동 분류가 필요합니다.")
            for f in batch:
                all_results[f] = {"folder_name": "미분류", "product_name": "미분류"}
        except Exception as e:
            print(f"   ⚠️  API 오류: {e}")
            for f in batch:
                all_results[f] = {"folder_name": "미분류", "product_name": "미분류"}

    return all_results


# ─── 수동 분류 ─────────────────────────────────────────────
def classify_manual(image_files):
    print(f"\n📸 총 {len(image_files)}장의 이미지를 수동 분류합니다.")
    print("   각 이미지를 확인하고 제품명(폴더명)을 입력해 주세요.\n")

    all_results = {}
    known_products = {}

    for i, fpath in enumerate(image_files):
        fname = os.path.basename(fpath)
        print(f"   [{i+1}/{len(image_files)}] {fname}")

        if known_products:
            print(f"   기존 제품: {', '.join(f'{k}({v})' for k,v in enumerate(known_products.keys(), 1))}")

        name = input("   → 제품명 (또는 번호 선택, 's' 건너뛰기): ").strip()

        if name == 's':
            all_results[fpath] = {"folder_name": "미분류", "product_name": "미분류"}
            continue

        if name.isdigit():
            idx = int(name) - 1
            keys = list(known_products.keys())
            if 0 <= idx < len(keys):
                name = keys[idx]

        if name not in known_products:
            brand = input("   → 브랜드: ").strip()
            category = input("   → 카테고리: ").strip()
            known_products[name] = {
                "product_name": name, "brand": brand, "category": category,
                "folder_name": name.replace(" ", "_").replace("/", "_"),
                "spec": "", "price_tag": "", "feature": "",
            }

        all_results[fpath] = known_products[name].copy()

    return all_results


# ─── 폴더 생성 & 이미지 이동 ─────────────────────────────────
def organize_files(source_folder, classification_results, auto_confirm=False):
    products = {}
    for fpath, info in classification_results.items():
        folder_name = info.get("folder_name", "미분류")
        if folder_name not in products:
            products[folder_name] = {"info": info, "files": []}
        products[folder_name]["files"].append(fpath)

    print(f"\n📁 {len(products)}개 제품으로 분류됩니다:")
    for name, data in products.items():
        print(f"   - {name}: {len(data['files'])}장")

    if not auto_confirm:
        confirm = input("\n이대로 폴더를 생성하고 이미지를 이동할까요? (y/n): ").strip().lower()
        if confirm != 'y':
            print("취소되었습니다.")
            return None

    for idx, (name, data) in enumerate(sorted(products.items()), 1):
        folder_path = os.path.join(source_folder, f"{idx:02d}_{name}")
        os.makedirs(folder_path, exist_ok=True)
        new_files = []
        for fpath in data["files"]:
            dest = os.path.join(folder_path, os.path.basename(fpath))
            if os.path.abspath(fpath) != os.path.abspath(dest):
                shutil.move(fpath, dest)
            new_files.append(dest)  # 이동 후 새 경로로 업데이트
        data["folder_path"] = folder_path
        data["files"] = new_files  # 실제 위치로 경로 갱신
        print(f"   ✅ {idx:02d}_{name}/ → {len(new_files)}장 이동 완료")

    return products


# ─── 이미 분류된 폴더 읽기 (AI 분석 포함) ──────────────────────
def read_existing_folders(base_folder, use_ai=True):
    """
    이미 분류된 폴더 구조를 읽고, Gemini AI로 제품 상세정보를 추출합니다.
    use_ai=True이면 Gemini Vision으로 이미지 분석
    """
    from config import GEMINI_API_KEY

    products = {}
    skip_dirs = {'매입자동화', '상세페이지', '쿠팡등록데이터', '__pycache__',
                 '.thumbnails', 'web_templates', 'web_static', 'templates'}

    folders_to_analyze = []
    for item in sorted(os.listdir(base_folder)):
        item_path = os.path.join(base_folder, item)
        if not os.path.isdir(item_path):
            continue
        if item.startswith(".") or item in skip_dirs:
            continue
        images = get_image_files(item_path)
        if not images:
            continue
        folders_to_analyze.append((item, item_path, images))

    if not folders_to_analyze:
        return products

    # AI 분석 가능 여부
    can_ai = use_ai and bool(GEMINI_API_KEY) and HAS_GENAI

    if can_ai:
        print(f"\n🤖 {len(folders_to_analyze)}개 폴더의 이미지를 Gemini AI로 분석합니다...")

    for idx, (item, item_path, images) in enumerate(folders_to_analyze, 1):
        clean_name = item.lstrip("0123456789_")

        if can_ai:
            print(f"   [{idx}/{len(folders_to_analyze)}] {item} ({len(images)}장) 분석 중...")
            ai_info = analyze_product_with_ai(images, item, GEMINI_API_KEY)
            if ai_info:
                ai_info["folder_name"] = item
                products[item] = {
                    "info": ai_info,
                    "files": images,
                    "folder_path": item_path,
                }
                pname = ai_info.get("product_name", clean_name)
                brand = ai_info.get("brand", "")
                print(f"      → {pname} ({brand})")
                continue

        # AI 실패 또는 미사용 시 폴더명 기반 기본값
        products[item] = {
            "info": {
                "product_name": clean_name,
                "brand": "", "category": "", "spec": "",
                "price_tag": "", "feature": "", "folder_name": item,
                "manufacturer": "", "origin": "", "ingredients": "",
                "usage": "", "certification": "", "barcode": "",
                "expiry_info": "", "package_type": "", "target_audience": "",
                "selling_point": "",
            },
            "files": images,
            "folder_path": item_path,
        }

    return products


# ─── 메인 실행 ─────────────────────────────────────────────
def run(source_folder):
    print("=" * 60)
    print("  STEP 1: 이미지 분석 & 제품별 폴더 분류")
    print("=" * 60)

    subdirs = [d for d in os.listdir(source_folder)
               if os.path.isdir(os.path.join(source_folder, d)) and not d.startswith(".")]
    has_subfolders = any(
        get_image_files(os.path.join(source_folder, d)) for d in subdirs
    )

    if has_subfolders:
        print(f"\n📂 이미 분류된 하위폴더가 감지되었습니다:")
        for d in sorted(subdirs):
            cnt = len(get_image_files(os.path.join(source_folder, d)))
            if cnt > 0:
                print(f"   - {d}/ ({cnt}장)")

        choice = input("\n기존 폴더 구조를 사용할까요? (y=기존사용 / n=새로 분류): ").strip().lower()
        if choice == 'y':
            products = read_existing_folders(source_folder)
            print(f"\n✅ {len(products)}개 제품 폴더 로드 완료")
            return products

    image_files = get_image_files(source_folder)
    if not image_files:
        print("\n⚠️  이미지 파일이 없습니다.")
        return None

    print(f"\n📸 루트 폴더에 {len(image_files)}장의 이미지가 있습니다.")

    from config import GEMINI_API_KEY
    if GEMINI_API_KEY and HAS_GENAI:
        print("\n🤖 Gemini AI 자동 분류 모드")
        results = classify_with_ai(image_files, GEMINI_API_KEY)
    else:
        if not HAS_GENAI:
            print("\n⚠️  google-genai 미설치 → 수동 분류 모드")
        else:
            print("\n🔧 수동 분류 모드 (Gemini API 키 없음)")
        results = classify_manual(image_files)

    products = organize_files(source_folder, results)
    return products


if __name__ == "__main__":
    folder = input("이미지 폴더 경로를 입력하세요: ").strip()
    if os.path.isdir(folder):
        run(folder)
    else:
        print(f"폴더를 찾을 수 없습니다: {folder}")
