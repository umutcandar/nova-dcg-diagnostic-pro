"""Conservative, unpowered-PCB measurement guidance. Not a fault diagnosis."""
GUIDES = {
    "Güç girişi": [
        "Kartın tüm güç bağlantılarını kesin ve kondansatörlerde artık gerilim olmadığını doğrulayın.",
        "Multimetreyi direnç moduna alın. Giriş besleme hattı ile GND arasını ölçün.",
        "Düşük direnç görürseniz şema, paralel yollar ve bağlı yükleri kontrol edin; kısa devre kesin değildir.",
    ],
    "Sigorta": [
        "Kartın enerjisiz olduğunu doğrulayın.",
        "Sigortanın iki ucu arasındaki direnci ölçün.",
        "Yüksek direnç/kopukluk varsa sigortayı devre koşullarıyla birlikte inceleyin.",
    ],
    "Diyot": [
        "Kartın enerjisiz ve kondansatörlerin deşarj edilmiş olduğunu doğrulayın.",
        "Diyot modunda ileri yön gerilimini ölçün.",
        "Probları ters çevirip ters yön sonucunu karşılaştırın; paralel yollar yanıltabilir.",
    ],
    "Kondansatör": [
        "Kartın enerjisiz olduğunu ve kondansatörün deşarj edildiğini uygun yöntemle doğrulayın.",
        "Gözle şişme, akma, çatlak veya yanık kontrolü yapın.",
        "Devre içi direnç okumasıyla tek başına kapasite/ESR veya sağlamlık kararı vermeyin.",
    ],
    "Direnç": [
        "Kartın enerjisiz olduğunu doğrulayın.",
        "Direncin iki ucu arasındaki değeri ölçün.",
        "Renk kodu, baskı veya şemadaki nominal değerle karşılaştırın; paralel yolları hesaba katın.",
    ],
}
def steps_for(component):
    return GUIDES.get(component, [])
