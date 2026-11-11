"""Conservative, model-independent multimeter guidance for offline PCB service.

Never infer nominal values or pinouts from a photo.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Guide:
    component: str
    mode: str
    setup: str
    probes: str
    expected: str
    next_step: str

GUIDES = {
    "resistor": Guide("Direnç","Ω","Enerjiyi kesin ve gerilimin olmadığını doğrulayın.","İki uca prob bağlayın; polarite önemli değildir.","Nominal direnç ve tolerans doğrulanmadan sayısal aralık gösterilmez.","Paralel yolları değerlendirin; gerekirse bir bacağı ayırarak tekrar ölçün."),
    "capacitor": Guide("Kapasitör","Kapasitans (F)","Enerjiyi kesin; güvenli şekilde deşarj edip gerilimi doğrulayın.","İki terminale prob bağlayın; polarize parçanın ve cihazın talimatlarına uyun.","Nominal kapasite, tolerans ve ölçüm koşulları doğrulanmalıdır.","Devre içi sonuç yanıltıcıysa güvenli biçimde ayırıp tekrar ölçün."),
    "diode": Guide("Diyot","Diyot testi","Enerjiyi kesin ve kondansatörleri güvenli deşarj edin.","İleri yön için kırmızı anot, siyah katot; ters yön için yer değiştirin.","İleri gerilim düşümü parçaya ve koşullara bağlıdır; sabit evrensel aralık yoktur.","İki yönde ölçün; paralel devre etkisini ve datasheet'i kontrol edin."),
    "mosfet": Guide("MOSFET","Diyot / Ω","Enerjiyi kesin, kapasitörleri güvenli deşarj edin; gate yükünü kontrol edin.","G/D/S pinleri yalnızca doğrulanmış datasheet ve paket yönüne göre belirlenir.","Model ve devre topolojisi bilinmeden kesin değer verilemez.","Önce pin eşlemesini doğrulayın, sonra kontrollü test planı uygulayın."),
    "ic": Guide("Entegre","Datasheet'e bağlı","Enerji ve ESD güvenliği için üretici talimatını izleyin.","Pin numarası, paket yönü ve test noktaları teknisyen tarafından doğrulanmalıdır.","Genel geçer pin voltajı yoktur; devre şeması ve datasheet gereklidir.","Besleme, toprak ve test koşullarını doğrulayarak uygun ölçüm planını oluşturun."),
}
ALIASES={"direnç":"resistor","kondansatör":"capacitor","kapasitör":"capacitor","diyot":"diode","entegre":"ic"}
def guide_for(component, nominal=None, tolerance_percent=None, unit=None):
    key=ALIASES.get(component.strip().lower(),component.strip().lower())
    if key not in GUIDES:
        return {"status":"ek bilgi gerekli","message":"Komponent tipi doğrulanmalı"}
    g=GUIDES[key]
    result={"component":g.component,"mode":g.mode,"setup":g.setup,"probes":g.probes,"expected":g.expected,"next_step":g.next_step}
    if nominal is not None or tolerance_percent is not None:
        if nominal is None or tolerance_percent is None or unit is None:
            result["expected"]="Sayısal aralık için nominal değer, birim ve tolerans birlikte doğrulanmalı."
        elif nominal < 0 or not 0 <= tolerance_percent <= 100:
            raise ValueError("Invalid nominal value or tolerance")
        elif key in ("resistor","capacitor"):
            delta=nominal*tolerance_percent/100
            result["expected"]=f"{nominal-delta:g}–{nominal+delta:g} {unit} (doğrulanmış {nominal:g} {unit} ±%{tolerance_percent:g}; devre dışı ölçüm için)"
    return result
