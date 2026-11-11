"""Component-specific safe measurement instructions.

Never infer exact probe pins from an image bounding box.
"""
GUIDANCE={
 "Direnç":("Direnç (Ω)","Enerjisiz kartta direnç uçları arasını ölç. Paralel yollar sonucu değiştirebilir."),
 "Kondansatör":("Kapasitans (F)","Önce gerilimin sıfır olduğunu doğrula. Kapasitans ölçümü için çoğu durumda devreden ayırma gerekir."),
 "Diyot":("Diyot (V)","Diyot modunda iki yönde ölç; polariteyi doğrula. Paralel devre yollarına dikkat et."),
 "Bobin":("Direnç (Ω)","Sargı sürekliliğini kontrol et; çok düşük direnç tek başına kısa devre değildir."),
 "MOSFET":("Diyot (V)","Parça kodu ve pin dizilimini datasheet ile doğrula; enerjisiz kartta gövde diyodunu iki yönde kontrol et."),
 "Transistör":("Diyot (V)","Parça kodundan BJT/MOSFET tipini ve pinleri doğrula; uygun bağlantı çiftlerini iki yönde ölç."),
 "Entegre":("Direnç (Ω)","Pinleri ve besleme hattını şema/datasheet ile doğrula; tek direnç ölçümü sağlamlık testi değildir."),
 "Konnektör":("Direnç (Ω)","Enerjisiz kartta bağlantı sürekliliğini şema üzerinden doğrula."),
 "LED":("Diyot (V)","LED polaritesini doğrula; enerjisiz ve deşarj edilmiş kartta diyot testi yap."),
 "Anahtar":("Direnç (Ω)","Enerjiyi kes; anahtar terminallerini doğrula, açık ve kapalı konumlarda sürekliliği karşılaştır."),
 "Header":("Direnç (Ω)","Pinleri şemayla eşleştir, enerjisiz bağlantı sürekliliğini test et."),
 "Kristal":("Datasheet gerekli","Kristal osilatörün doğru çalıştığı basit Fluke ölçümüyle anlaşılmaz; yöntemini doğrula."),
 "Test noktası":("Devre şeması gerekli","Test noktasının işlevi şema olmadan tahmin edilemez."),
 "Bilinmiyor":("Direnç (Ω)","Ölçümden önce komponent türünü ve pinleri doğrula.")
}
def instruction_for(component):
    return GUIDANCE.get(component,GUIDANCE["Bilinmiyor"])
