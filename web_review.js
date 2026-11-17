/* NOVA DCG web-only, pure review rules. No network, disk, inference or secrets. */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.NovaReview = api;
})(typeof globalThis !== "undefined" ? globalThis : null, function() {
  "use strict";

  const CLASSES = Object.freeze([
    "Direnç", "Kondansatör", "Diyot", "Entegre", "Transistör",
    "Bobin", "Konnektör", "Bilinmiyor", "MOSFET", "LED",
    "Anahtar", "Header", "Kristal", "Test noktası"
  ]);

  function validBox(box, width, height) {
    if (!Array.isArray(box) || box.length !== 4 ||
        !box.every(x => typeof x === "number" && Number.isFinite(x))) return false;
    return box[0] >= 0 && box[1] >= 0 &&
      box[0] < box[2] && box[1] < box[3] &&
      box[2] <= width && box[3] <= height;
  }

  function trainingAnnotation({boardId, image, width, height, regions, completedReview}) {
    if (typeof boardId !== "string" || !/^[a-zA-Z0-9_-]{3,64}$/.test(boardId.trim())) {
      throw Error("Kart kimliği 3–64 karakter olmalı (harf, rakam, - veya _).");
    }
    if (typeof image !== "string" || !image.trim() || /[/\\]/.test(image) ||
        image.includes("..") || image.length > 180) {
      throw Error("Fotoğraf adı geçersiz. Orijinal JPG/PNG/WebP dosyasını kullan.");
    }
    if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1) {
      throw Error("Fotoğraf boyutları geçersiz.");
    }
    if (!completedReview) {
      throw Error("Fotoğraftaki bütün görünür parçaları kontrol edip işaretlediğini onayla.");
    }
    if (!Array.isArray(regions) || regions.length === 0) {
      throw Error("Eğitim için en az bir onaylanmış komponent gereklidir.");
    }
    const verified = [];
    for (const r of regions) {
      if (!r || !r.confirmed || !CLASSES.includes(r.label) || r.label === "Bilinmiyor") {
        throw Error("Bütün işaretleri doğrula; yanlış adayları sil, bilinmeyenleri doğru etiketle.");
      }
      if (!validBox(r.bbox_xyxy_pixels, width, height)) {
        throw Error("Komponent kutusu fotoğraf sınırları dışında.");
      }
      const b = r.bbox_xyxy_pixels;
      verified.push({
        label: r.label,
        bbox_xyxy_normalized: [b[0]/width, b[1]/height, b[2]/width, b[3]/height]
      });
    }
    return {
      coordinate_system: "xyxy_normalized",
      board_id: boardId.trim(),
      image: image.trim(),
      technician_verified: true,
      regions: verified,
      annotation_source: "nova-dcg-web-manual-review",
      image_coordinate_space: "exif_transposed",
      image_width: width,
      image_height: height
    };
  }

  function parseDecimal(value) {
    if (typeof value === "number") return Number.isFinite(value) && value >= 0 ? value : null;
    const cleaned = String(value == null ? "" : value).trim().replace(",", ".");
    if (!/^\d+(?:\.\d+)?$/.test(cleaned)) return null;
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : null;
  }

  const MODE_UNITS = Object.freeze({
    resistance: "Ω", diode: "V", capacitance: "µF", continuity: "Ω"
  });

  function evaluateReference({
    reading, mode, circuitState, referenceMode, referenceState,
    minimum, maximum, sourceUrl, conditions, partNumber, technicianVerified
  }) {
    const value = parseDecimal(reading), low = parseDecimal(minimum), high = parseDecimal(maximum);
    if (!(mode in MODE_UNITS) || !["in_circuit","out_of_circuit"].includes(circuitState) ||
        value === null || low === null || high === null || low > high) {
      throw Error("Ölçüm ve referans için geçerli, negatif olmayan sayılar ve koşullar gerekli.");
    }
    if (referenceMode !== mode || referenceState !== circuitState) {
      throw Error("Referans modu ve devre içi/dışı koşulu ölçümle aynı olmalı.");
    }
    if (typeof sourceUrl !== "string" || !/^https:\/\/[^/\s]+\.[^/\s]+(?:\/\S*)?$/.test(sourceUrl)) {
      throw Error("Kaynağın HTTPS bağlantısını doğrula.");
    }
    if (typeof partNumber !== "string" || partNumber.trim().length < 2 ||
        typeof conditions !== "string" || !conditions.trim() || technicianVerified !== true) {
      throw Error("Parça/nominal tanımı, üretici test koşulları ve teknisyen onayı gerekli.");
    }
    if (circuitState === "in_circuit") {
      return {
        code: "needs_review",
        message: "Ölçüm kaydedildi. Devre içi paralel yollar nedeniyle referansla tek ölçümden karar verilemez."
      };
    }
    return value >= low && value <= high ?
      {code:"within",message:"Doğrulanmış referans aralığında. Bu, tek başına parçanın sağlam olduğunu kanıtlamaz."} :
      {code:"outside",message:"Doğrulanmış referans aralığı dışında. Ölçüm, koşullar ve parça kodunu yeniden doğrula."};
  }

  return Object.freeze({CLASSES, MODE_UNITS, validBox, trainingAnnotation, parseDecimal, evaluateReference});
});
