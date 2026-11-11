"""General component checks; not board-specific diagnosis.

Only measure resistance/continuity on isolated, discharged boards.
"""
COMPONENTS={
    "Direnç":{"function":"Akımı sınırlama ve gerilim bölme",
              "checks":["Enerji kesilip kondansatörler boşaltıldıktan sonra direnç ölç",
                        "Devre içi paralel yolların sonucu değiştirebileceğini kontrol et"],
              "caution":"Devre içi direnç değeri nominal değerden düşük çıkabilir."},
    "Kondansatör":{"function":"Filtreleme, kuplaj ve enerji depolama",
                  "checks":["Güvenli şekilde deşarj edildiğini doğrula",
                            "Uygun cihaz varsa kapasitans/ESR ölç"],
                  "caution":"Ohm modundaki tek ölçüm kondansatörün sağlamlığını kanıtlamaz."},
    "Diyot":{"function":"Akımı tercih edilen yönde iletme",
             "checks":["Diyot modunda her iki yönü ölç","Paralel yollar varsa devre dışı doğrula"],
             "caution":"Düşük değer kısa devreyi tek başına kanıtlamaz."},
    "Entegre":{"function":"Kart üzerinde belirli kontrol veya sinyal işlevi",
               "checks":["Parça kodunu ve üretici veri sayfasını doğrula",
                         "Enerjisiz kartta besleme hattı-toprak kısa devre taraması yap"],
               "caution":"Pin dizilimi ve beklenen değerler entegre modeline bağlıdır."},
    "Transistör":{"function":"Anahtarlama veya yükseltme",
                  "checks":["Parça tipini ve pin dizilimini veri sayfasından doğrula",
                            "Uygun diyot modu kontrollerini yap"],
                  "caution":"MOSFET ve BJT için aynı ölçüm yorumu kullanılmaz."},
    "Bobin":{"function":"Manyetik enerji depolama ve filtreleme",
             "checks":["Sargı sürekliliğini kontrol et","Değeri şema veya sağlam kartla karşılaştır"],
             "caution":"Düşük DC direnç birçok bobin için normaldir."},
    "Konnektör":{"function":"Kartlar ve kablolar arası bağlantı",
                 "checks":["Pin oksidasyonu ve mekanik hasarı incele",
                           "Enerjisiz halde uçtan uca süreklilik kontrolü yap"],
                 "caution":"Konnektör pinlerini kısa devre etmemeye dikkat et."}
}
def component_info(name):
    if name not in COMPONENTS:
        raise KeyError(f"Unknown component: {name}")
    return COMPONENTS[name].copy()
