# ai_engine/image_finder.py
"""
Wikimedia Commons görsel bulucu.

- Her sahne için yalnızca bir arama döngüsü çalıştırır.
- HTTP 429 ve geçici sunucu hatalarında kontrollü yeniden dener.
- Wikimedia hız sınırına takılındığında kalan sahneleri gereksiz isteklerle
  zorlamaz; bulunan görselleri manifest'e kaydeder.
- Görsel bulunamayan sahneler manifest'e sahnesiz/boş kayıt eklemez.
"""

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from config.settings import PLAN_PATH, ASSETS_DIR, MANIFEST_PATH


API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "DocumentaryAutomation/3.1 (Wikimedia Commons image search)"
}

MAX_RETRIES = 3
MIN_IMAGE_BYTES = 15_000
SEARCH_RESULT_LIMIT = 5
REQUEST_TIMEOUT = 35


class RateLimitError(Exception):
    """Wikimedia Commons isteği 429 ile reddedildiğinde kullanılır."""


def _retry_delay(error, attempt):
    """Retry-After varsa onu, yoksa artan bekleme süresini kullan."""
    retry_after = None
    if isinstance(error, urllib.error.HTTPError):
        retry_after = error.headers.get("Retry-After")

    if retry_after:
        try:
            return min(max(float(retry_after), 1.0), 90.0)
        except (TypeError, ValueError):
            pass

    return min(5 * (2 ** attempt) + random.uniform(0.5, 2.0), 60.0)


def _read_url(url, timeout=REQUEST_TIMEOUT):
    """
    URL'yi indirir/okur. 429 ve 5xx hatalarında sınırlı yeniden deneme yapar.
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        request = urllib.request.Request(url, headers=HEADERS)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()

        except urllib.error.HTTPError as error:
            last_error = error

            if error.code == 429:
                if attempt >= MAX_RETRIES:
                    raise RateLimitError(
                        "Wikimedia Commons hız sınırı (HTTP 429); "
                        "yeniden deneme sınırı aşıldı."
                    ) from error

            elif 500 <= error.code <= 599:
                if attempt >= MAX_RETRIES:
                    raise
            else:
                raise

            delay = _retry_delay(error, attempt)
            print(
                f"     [BEKLEME] HTTP {error.code}; "
                f"{delay:.1f} saniye sonra tekrar denenecek "
                f"({attempt + 1}/{MAX_RETRIES})."
            )
            time.sleep(delay)

        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt >= MAX_RETRIES:
                raise

            delay = _retry_delay(error, attempt)
            print(
                f"     [BEKLEME] Bağlantı hatası: {error}; "
                f"{delay:.1f} saniye sonra tekrar denenecek."
            )
            time.sleep(delay)

    raise last_error or RuntimeError("İstek tamamlanamadı.")


def request_json(url):
    raw_data = _read_url(url)
    data = json.loads(raw_data.decode("utf-8"))

    if "error" in data:
        api_error = data["error"]
        raise RuntimeError(
            f"Wikimedia API hatası: {api_error.get('code', 'unknown')} - "
            f"{api_error.get('info', 'Açıklama yok')}"
        )

    return data


def _valid_image(data):
    """İndirilen verinin desteklenen bir görsel formatı olduğunu doğrula."""
    if len(data) < MIN_IMAGE_BYTES:
        raise ValueError(
            f"Görsel dosyası çok küçük ({len(data) // 1024} KB)."
        )

    if data.startswith(b"\xff\xd8\xff"):  # JPEG
        return ".jpg"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return ".png"

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":  # WebP
        return ".webp"

    raise ValueError("İndirilen dosya JPEG, PNG veya WebP değil.")


def download_image(url, path):
    data = _read_url(url, timeout=50)
    extension = _valid_image(data)

    # Uzantıyı içerikten belirle; URL uzantısına güvenme.
    root, _old_extension = os.path.splitext(path)
    final_path = root + extension
    temporary_path = final_path + ".part"

    try:
        with open(temporary_path, "wb") as file:
            file.write(data)
        os.replace(temporary_path, final_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

    return len(data), final_path


def search_images(query):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query + " filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": SEARCH_RESULT_LIMIT,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1920,
    }

    url = API_URL + "?" + urllib.parse.urlencode(params)
    data = request_json(url)
    pages = data.get("query", {}).get("pages", {})
    results = []

    for page in pages.values():
        info_list = page.get("imageinfo", [])
        if not info_list:
            continue

        info = info_list[0]
        image_url = info.get("thumburl") or info.get("url", "")
        if not image_url:
            continue

        extension = os.path.splitext(
            urllib.parse.urlparse(image_url).path
        )[1].lower()

        if extension not in (".jpg", ".jpeg", ".png", ".webp"):
            continue

        metadata = info.get("extmetadata", {})

        results.append({
            "title": page.get("title", ""),
            "image_url": image_url,
            "source_url": info.get("descriptionurl", ""),
            "license": metadata.get(
                "LicenseShortName", {}
            ).get("value", "Unknown"),
            "artist": metadata.get("Artist", {}).get("value", "Unknown"),
            "description": metadata.get(
                "ImageDescription", {}
            ).get("value", "")[:500],
        })

    return results


def score_image_relevance(image_data, scene):
    search_text = (
        image_data.get("title", "") + " " +
        image_data.get("description", "")
    ).lower()

    scene_keywords = set(
        scene.get("visual_description", "").lower().split()
        + scene.get("narration_summary", "").lower().split()
    )

    for query in scene.get("image_search_queries", []):
        scene_keywords.update(query.lower().split())

    stop_words = {
        "the", "a", "an", "and", "or", "in", "on", "of", "to",
        "with", "by", "for", "from", "that", "this", "is", "are",
    }

    scene_keywords = {
        word.strip(".,!?;:()[]{}\"'")
        for word in scene_keywords
        if word not in stop_words and len(word) > 2
    }

    return sum(1 for word in scene_keywords if word and word in search_text)


def _scene_queries(scene):
    """Tekrarlanan veya boş sorguları temizle; alakasız tarih fallback'i ekleme."""
    queries = scene.get("image_search_queries", [])
    cleaned = []
    seen = set()

    for query in queries:
        if not isinstance(query, str):
            continue
        query = query.strip()
        key = query.casefold()
        if query and key not in seen:
            cleaned.append(query)
            seen.add(key)

    return cleaned


def find_images():
    if not os.path.exists(PLAN_PATH):
        print("Hata: scene_plan.json bulunamadı. Önce main.py'yi çalıştırın.")
        return

    with open(PLAN_PATH, "r", encoding="utf-8") as file:
        plan = json.load(file)

    scenes = plan.get("scenes", [])
    os.makedirs(ASSETS_DIR, exist_ok=True)
    manifest = []
    rate_limited = False

    for scene_index, scene in enumerate(scenes):
        scene_id = int(scene["id"])
        queries = _scene_queries(scene)

        print(f"\nSahne {scene_id} için görsel aranıyor...")

        if not queries:
            print("  -> Bu sahne için arama sorgusu tanımlanmamış; atlanıyor.")
            continue

        image_found = False
        tried_urls = set()

        for query_index, query in enumerate(queries):
            print(f"  -> Sorgu deneniyor: '{query}'")

            try:
                results = search_images(query)
            except RateLimitError as error:
                print(f"  [DURDURULDU] {error}")
                rate_limited = True
                break
            except Exception as error:
                print(f"     Arama hatası: {error}")
                # Bir sorgu başarısızsa sahnenin diğer sorgusunu deneyebilir.
                continue

            ranked_results = sorted(
                results,
                key=lambda item: score_image_relevance(item, scene),
                reverse=True,
            )

            for result in ranked_results:
                image_url = result.get("image_url", "")
                if not image_url or image_url in tried_urls:
                    continue
                tried_urls.add(image_url)

                base_path = os.path.join(
                    ASSETS_DIR, f"scene_{scene_id:02d}"
                )

                try:
                    size, final_path = download_image(image_url, base_path)
                    filename = os.path.basename(final_path)
                    score = score_image_relevance(result, scene)

                    manifest.append({
                        "scene_id": scene_id,
                        "filename": filename,
                        "local_path": final_path,
                        "source_url": result.get("source_url", ""),
                        "license": result.get("license", "Unknown"),
                        "artist": result.get("artist", "Unknown"),
                        "title": result.get("title", ""),
                        "file_size_bytes": size,
                        "match_score": score,
                    })

                    print(
                        f"     [BAŞARILI] İndirildi: {filename} "
                        f"(Skor: {score}, Boyut: {size // 1024} KB)"
                    )
                    image_found = True
                    break

                except RateLimitError as error:
                    print(f"  [DURDURULDU] {error}")
                    rate_limited = True
                    break
                except Exception as error:
                    print(f"     [UYARI] Görsel indirilemedi: {error}")

            if image_found or rate_limited:
                break

            # Wikimedia'ya arka arkaya istek göndermemek için kısa ara.
            if query_index < len(queries) - 1:
                time.sleep(3 + random.uniform(0.5, 1.5))

        if not image_found:
            print(f"Sahne {scene_id} için görsel bulunamadı.")

        if rate_limited:
            remaining = len(scenes) - scene_index - 1
            if remaining:
                print(
                    f"[BİLGİ] Hız sınırı nedeniyle kalan {remaining} "
                    "sahnenin araması bu çalıştırmada atlanıyor."
                )
            break

        # Sahneler arasında Wikimedia'ya nefes aldır.
        if scene_index < len(scenes) - 1:
            time.sleep(3 + random.uniform(1, 2))

    manifest_dir = os.path.dirname(MANIFEST_PATH)
    if manifest_dir:
        os.makedirs(manifest_dir, exist_ok=True)

    with open(MANIFEST_PATH, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4, ensure_ascii=False)

    print(
        f"\nGörsel indirme tamamlandı. Toplam: "
        f"{len(manifest)} / {len(scenes)}"
    )
    print(f"Manifest kaydedildi: {MANIFEST_PATH}")

    if rate_limited:
        print(
            "Not: Wikimedia hız sınırına takıldı. Bir süre bekleyip "
            "yeniden çalıştırabilirsiniz."
        )


if __name__ == "__main__":
    find_images()
