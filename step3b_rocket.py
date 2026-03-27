"""
STEP 3-2 — 쿠팡 판매 확인 + 최저가 비교

네이버 쇼핑 API를 활용하여:
  - 해당 제품이 쿠팡에서 판매 중인지 확인
  - 쿠팡 최저가 추출
  - 쿠팡 판매 여부를 엑셀에 자동 표기

※ 쿠팡 직접 크롤링은 Akamai CDN에서 봇을 차단(403)하기 때문에
   네이버 쇼핑 API 결과에서 mallName='쿠팡'인 항목을 필터링하는 방식 사용
"""
import os, json, time, re
import urllib.request, urllib.parse
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

try:
    from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_DISPLAY
except ImportError:
    NAVER_CLIENT_ID = ""
    NAVER_CLIENT_SECRET = ""
    NAVER_DISPLAY = 20

# ─── 스타일 상수 ─────────────────────────────────────────
COUPANG_COLOR = "6C3483"
ROCKET_GREEN  = "27AE60"
GRAY_TEXT     = "AAAAAA"

def _fill(c):
    return PatternFill("solid", start_color=c, fgColor=c)

def _border():
    s = Side(style="thin", color="BBBBBB")
    return Border(left=s, right=s, top=s, bottom=s)


# ─── 네이버 쇼핑에서 쿠팡 판매 제품 검색 ─────────────────
def search_naver_for_coupang(query, display=20):
    """
    네이버 쇼핑 API로 검색 → mallName='쿠팡'인 결과 필터링.
    쿠팡 최저가와 판매 여부를 반환.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/shop.json?query={encoded}&display={display}&sort=asc"

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items", [])
    except Exception as e:
        print(f"   ⚠️  네이버 검색 오류: {e}")
        return {"all_items": [], "coupang_items": []}

    all_items = []
    coupang_items = []

    for item in items:
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        mall = item.get("mallName", "")
        link = item.get("link", "")
        try:
            price = int(item.get("lprice", 0))
        except (ValueError, TypeError):
            price = 0

        parsed = {
            "title": title,
            "mall": mall,
            "price": price,
            "link": link,
            "image": item.get("image", ""),
        }
        all_items.append(parsed)

        # 쿠팡 판매 여부 확인
        is_coupang = (
            "쿠팡" in mall
            or "coupang" in mall.lower()
            or "coupang" in link.lower()
        )
        if is_coupang and price > 0:
            coupang_items.append(parsed)

    return {
        "all_items": all_items,
        "coupang_items": coupang_items,
    }


def analyze_coupang_status(search_result):
    """검색 결과를 분석해서 쿠팡 판매 상태 정리"""
    coupang_items = search_result.get("coupang_items", [])
    all_items = search_result.get("all_items", [])

    if not coupang_items:
        return {
            "on_coupang": False,
            "coupang_price": 0,
            "coupang_price_str": "",
            "coupang_count": 0,
            "coupang_title": "",
            "coupang_link": "",
            "total_results": len(all_items),
            "status_text": "쿠팡 미판매",
        }

    # 쿠팡 최저가
    lowest = min(coupang_items, key=lambda x: x["price"])

    return {
        "on_coupang": True,
        "coupang_price": lowest["price"],
        "coupang_price_str": f"{lowest['price']:,}원",
        "coupang_count": len(coupang_items),
        "coupang_title": lowest["title"],
        "coupang_link": lowest["link"],
        "total_results": len(all_items),
        "status_text": f"쿠팡 판매중 ({len(coupang_items)}건)",
    }


# ─── 엑셀 업데이트 ──────────────────────────────────────
def update_excel(excel_path, product_list):
    """엑셀 파일의 쿠팡 컬럼 (23: 쿠팡 최저가, 24: 쿠팡 판매) 업데이트"""
    wb = load_workbook(excel_path)
    ws = wb.active
    border = _border()

    results = []
    total = len(product_list)

    for i, product in enumerate(product_list):
        row = product["row"]
        name = product["name"]
        brand = product.get("brand", "")

        query = f"{brand} {name}".strip() if brand else name
        print(f"   [{i+1}/{total}] 검색: {query}")

        search_result = search_naver_for_coupang(query)
        status = analyze_coupang_status(search_result)

        shade = "F5F5F5" if i % 2 == 0 else "FFFFFF"

        col_cprice = 23  # W: 쿠팡 최저가
        col_status = 24  # X: 쿠팡 판매 상태

        if status["on_coupang"]:
            # 쿠팡 최저가
            c_price = ws.cell(row=row, column=col_cprice)
            c_price.value = status["coupang_price_str"]
            c_price.font = Font(name="맑은 고딕", bold=True, size=10, color="C00000")
            c_price.fill = _fill(shade)
            c_price.alignment = Alignment(horizontal="center", vertical="center")
            c_price.border = border

            # 쿠팡 판매 상태
            c_status = ws.cell(row=row, column=col_status)
            c_status.value = f"판매중 ({status['coupang_count']}건)"
            c_status.font = Font(name="맑은 고딕", bold=True, size=10, color=ROCKET_GREEN)
            c_status.fill = _fill(shade)
            c_status.alignment = Alignment(horizontal="center", vertical="center")
            c_status.border = border

            print(f"      → 쿠팡 {status['coupang_price_str']} ({status['coupang_count']}건)")
        else:
            # 쿠팡 미판매
            c_price = ws.cell(row=row, column=col_cprice)
            c_price.value = "-"
            c_price.font = Font(name="맑은 고딕", size=9, color=GRAY_TEXT)
            c_price.fill = _fill(shade)
            c_price.alignment = Alignment(horizontal="center", vertical="center")
            c_price.border = border

            c_status = ws.cell(row=row, column=col_status)
            c_status.value = "미판매"
            c_status.font = Font(name="맑은 고딕", size=9, color=GRAY_TEXT)
            c_status.fill = _fill(shade)
            c_status.alignment = Alignment(horizontal="center", vertical="center")
            c_status.border = border

            print(f"      → 쿠팡 미판매")

        results.append({
            "product_name": name,
            "on_coupang": status["on_coupang"],
            "coupang_price": status["coupang_price"],
            "coupang_price_str": status["coupang_price_str"],
            "coupang_count": status["coupang_count"],
            "coupang_link": status["coupang_link"],
            "status_text": status["status_text"],
        })

        time.sleep(0.3)  # API 호출 간격

    wb.save(excel_path)
    print(f"\n✅ 엑셀 업데이트 완료 → {excel_path}")
    return results


# ─── 메인 실행 ─────────────────────────────────────────
def run(product_list, excel_path):
    print("=" * 60)
    print("  STEP 3-2: 쿠팡 판매 확인")
    print("=" * 60)

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("\n⚠️  네이버 API 키가 설정되지 않았습니다.")
        print("   config.py에서 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET을 설정해 주세요.")
        print("   (쿠팡 크롤링은 봇 차단으로 불가하여 네이버 쇼핑 API를 활용합니다)")
        return []

    if not product_list:
        print("\n⚠️  제품 목록이 없습니다. Step 2를 먼저 실행해 주세요.")
        return []

    if not excel_path or not os.path.exists(excel_path):
        print(f"\n⚠️  엑셀 파일을 찾을 수 없습니다: {excel_path}")
        return []

    print(f"\n🔍 {len(product_list)}개 제품의 쿠팡 판매 여부를 확인합니다...")
    print(f"   (네이버 쇼핑 API → mallName='쿠팡' 필터링)\n")

    results = update_excel(excel_path, product_list)

    # 요약
    on_coupang = sum(1 for r in results if r.get("on_coupang"))
    print(f"\n📊 쿠팡 확인 결과:")
    print(f"   - 쿠팡 판매중: {on_coupang}/{len(results)}개")
    print(f"   - 쿠팡 미판매: {len(results) - on_coupang}/{len(results)}개")

    for r in results:
        icon = "🟢" if r["on_coupang"] else "⚪"
        price = r.get("coupang_price_str", "-") or "-"
        print(f"   {icon} {r['product_name']}: {price} ({r['status_text']})")

    return results


if __name__ == "__main__":
    print("이 모듈은 main.py를 통해 실행해 주세요.")
