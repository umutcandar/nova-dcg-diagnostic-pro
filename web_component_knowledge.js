/* NOVA DCG component marking knowledge.
   Nominal marking calculations are not validated electrical measurements.
   User confirmation is required for codes: photos and object detector cannot
   reliably read tiny marks/color bands or infer in-circuit readings.
*/
(function(root, factory) {
  const api=factory();
  if(typeof module==="object" && module.exports) module.exports=api;
  if(root) root.NovaKnowledge=api;
})(typeof globalThis!=="undefined"?globalThis:null,function(){
  "use strict";
  const DIGITS=Object.freeze({siyah:0,kahverengi:1,kirmizi:2,turuncu:3,sari:4,yesil:5,mavi:6,mor:7,gri:8,beyaz:9});
  const MULTIPLIER=Object.freeze({...DIGITS,altin:-1,gumus:-2});
  const TOLERANCE=Object.freeze({kahverengi:1,kirmizi:2,yesil:0.5,mavi:0.25,mor:0.1,gri:0.05,altin:5,gumus:10});
  const LABELS=Object.freeze(["Direnç","Kondansatör","Diyot","Entegre","Transistör","Bobin","Konnektör","Bilinmiyor","MOSFET","LED","Anahtar","Header","Kristal","Test noktası","Trimpot","Batarya","Buzzer","Ekran","Sigorta","Soğutucu","Pad","Pin","Röle","Trafo","Elektrolitik Kondansatör","Zener Diyot","Ferrit Boncuk","Jumper"]);
  const GUIDES=Object.freeze({
    "Direnç": {mode:"resistance", title:"Direnç (Ω)", probes:"İki uç arasında ölç. Polarite önemli değil.", explanation:"Nominal Ω değeri direnç üzerindeki işaretten veya renk bantlarından hesaplanabilir. Devre içi paralel yollar okumayı değiştirebilir."},
    "Trimpot": {mode:"resistance",title:"Direnç (Ω)",probes:"Üç uçlu ayarlı dirençtir. Yalnızca doğrulanmış pin dizilimine göre dış uçlar arasında toplam direnci, sürgü (wiper) ve uç arasında ayar değerini ölç.",explanation:"Üstteki vida ayarı değiştirir; sürgüye ait direnç sabit değildir. Örn. 103 kodu standart 3 rakamlı direnç koduysa 10 kΩ nominal toplam yol demektir. Fotoğraftan kesin pin sırası ve değer belirlenemez."},
    "Kondansatör":{mode:"capacitance",title:"Kapasitans (µF)",probes:"Enerjiyi kapat; güvenli deşarj ve artık gerilim kontrolünden sonra iki doğru terminali ölç.",explanation:"Kapasitans parça üzerindeki µF/nF/pF işaretinden veya belgeli koddansa okunabilir. Üzerindeki V değeri dayanım sınıfıdır, kartta beklenen besleme voltajı değildir."},
    "Diyot":{mode:"diode",title:"Diyot modu (V)",probes:"Anot-katodu işaret ve datasheet ile doğrula. İleri yönde kırmızı prob anotta, siyah prob katotta; sonra ters yönde ölç.",explanation:"Yaygın silisyum PN diyotta ileri yönde yaklaşık 0,5–0,8 V görülebilir (Fluke). Bu evrensel sınır değildir; Schottky, Zener, LED ve devre içindeki paralel yollar değiştirir.",kind:"typical",typical_range:[0.5,0.8],unit:"V",source:"https://www.fluke.com/en-us/learn/blog/digital-multimeters/how-to-test-diodes"},
    "LED":{mode:"diode",title:"Diyot modu (V)",probes:"Anot-katodu işaretten/datasheetten doğrula; ileri ve ters yönleri ayrı ölç.",explanation:"İleri gerilim LED rengine ve tipine bağlıdır; fotoğrafa göre evrensel aralık atanamaz."},
    "Bobin":{mode:"resistance",title:"Direnç (Ω)",probes:"Sargının iki ucunu doğrula ve düşük direnç/sürekliliği kontrol et.",explanation:"Düşük DC direnç normal olabilir. Bobin endüktansı yalnızca Fluke Ω ile doğrulanamaz."},
    "MOSFET":{mode:"diode",title:"Diyot / Ω",probes:"G/D/S pinlerini doğrulanmış parça kodu ve datasheetten eşleştir. Gate yükü ve ESD kurallarını izle.",explanation:"Kılıf benzerliğinden pin dizilimi veya kesin body-diyot değeri çıkarılamaz."},
    "Transistör":{mode:"diode",title:"Diyot (V)",probes:"B/E/C uçları ancak parça kodu ve datasheet ile belirlenebilir; yönlere göre ölç.",explanation:"NPN/PNP tipleri ve devre bağlantısı olmadan kesin sayısal aralık atanamaz."},
    "Entegre":{mode:"resistance",title:"Datasheet / şema",probes:"Parça kodu, besleme/toprak pinleri ve test koşulları doğrulanmadan rasgele pinlere prob bağlama.",explanation:"Entegre için genel geçer sağlam pin voltajı veya direnç aralığı yoktur."},
    "Konnektör":{mode:"continuity",title:"Süreklilik (Ω)",probes:"Şemadan hattın iki gerçek ucunu doğrulayıp ölç.",explanation:"Kart bağlantıları/paralel yollar bilinmeden sabit geçer-kalır eşiği yoktur."},
    "Anahtar":{mode:"continuity",title:"Süreklilik (Ω)",probes:"Doğru kontak çiftini, açık ve kapalı konumda ayrı ölç.",explanation:"Kontak tipi ve paralel yolları doğrula."},
    "Header":{mode:"continuity",title:"Süreklilik (Ω)",probes:"Şemada karşılık gelen pinleri doğrula.",explanation:"Pin numarası/işlevi fotoğrafa bakılarak güvenle belirlenemez."},
    "Kristal":{mode:"resistance",title:"Uygun cihaz gerekli",probes:"Parça datasheeti ve uygun osilatör testi gerekir.",explanation:"Fluke Ω ile frekans veya rezonans sağlığı doğrulanmaz."},
    "Test noktası":{mode:"resistance",title:"Şema gerekli",probes:"Şemadan neti ve uygun test koşullarını doğrula.",explanation:"Fotoğraftan beklenen voltaj bilinemez."},
    "Batarya":{mode:"none",title:"Enerjisiz test kapsamında değil",probes:"Bataryaya Ω veya diyot modu probunu rastgele bağlama; kimyasına uygun üretici güvenlik prosedürü gerekir.",explanation:"Batarya kimyası ve terminal şeması olmadan ölçüm aralığı bilinemez."},
    "Buzzer":{mode:"none",title:"Üretici testi gerekli",probes:"Piezo/aktif/pasif buzzer türü ve üretici prosedürü belirlenmeli.",explanation:"Buzzer için evrensel Ω veya voltaj aralığı yoktur."},
    "Ekran":{mode:"none",title:"Şema gerekli",probes:"Ekran konnektörlerine datasheet olmadan prob bağlama.",explanation:"Besleme ve veri pinleri tipe özgüdür."},
    "Sigorta":{mode:"continuity",title:"Süreklilik (Ω)",probes:"Enerji kesildikten, artık gerilim güvenli seviyede doğrulandıktan sonra sigortanın iki terminalini ölç.",explanation:"Kontak/hat topolojisini ve paralel yolları dikkate al; türüne göre üretici sınırları değişir."},
    "Soğutucu":{mode:"none",title:"Pasif mekanik parça",probes:"Elektriksel ölçüm yerine mekanik montajı ve yalıtımı doğrula.",explanation:"Soğutucunun sabit elektriksel direnç aralığı yoktur."},
    "Pad":{mode:"none",title:"PCB bağlantı yüzeyi",probes:"Şemada net/bağlantı bulunmadan rastgele test noktası sanıp prob bağlama.",explanation:"Pad parça değeri taşımaz; şema gerekir."},
    "Pin":{mode:"none",title:"Şema gerekli",probes:"Bilinmeyen pinlere rastgele ölçüm uygulama.",explanation:"Pin işlevi ve beklenen voltaj fotoğraftan çıkarılamaz."},
    "Röle":{mode:"resistance",title:"Bobin Ω / kontak sürekliliği",probes:"Bobin ve kontakları parça datasheetine göre ayır; sadece enerjisiz ölç.",explanation:"Bobin direnci ve kontak yapısı modele bağlıdır, evrensel aralık yoktur."},
    "Trafo":{mode:"resistance",title:"Sargı sürekliliği",probes:"Yüksek gerilim riski yokken sadece şemada doğrulanmış aynı sargının uçlarında ölç.",explanation:"Sargı direnci devreye göre değişir; düşük Ω tek başına kısa devre kanıtı değildir."},
    "Elektrolitik Kondansatör":{mode:"capacitance",title:"Kapasitans (µF)",probes:"Enerjiyi kes ve büyük kapasitörün artık gerilimini uygun şekilde kontrol et; güvenli biçimde deşarj et. Polariteyi doğrula, ölçümü uygun cihazla yap.",explanation:"Polarize elektrolitik kapasitördür. Nominal µF ve V işareti kapasitans ile dayanım gerilimini gösterir; V değeri karttaki çalışma gerilimi değildir. ESR ve kaçak akım için uygun cihaz ve üretici koşulları gerekir."},
    "Zener Diyot":{mode:"diode",title:"Diyot modu (V)",probes:"Anot ve katodu işaret/datasheet ile doğrula. Fluke diyot modunda ileri yöndeki davranışı kontrol et; ters kırılma gerilimini bu testten çıkarma.",explanation:"Zener ters kırılma gerilimi genellikle Fluke diyot modunda ölçülemez. Doğrulanmış zener kodu, kontrollü akım sınırlamalı test düzeni ve datasheet olmadan ters yönde sayısal sınır/uygulama verilmez."},
    "Ferrit Boncuk":{mode:"resistance",title:"Direnç (Ω)",probes:"Enerjisiz devrede, iki terminali net şema ile doğrulayarak ölç. Parça yolunu kısa devre sanma.",explanation:"Ferrit boncukta düşük DC direnç normal olabilir; yüksek frekans empedansını Fluke Ω modu göstermez. Fotoğraftan nominal empedans aralığı bilinemez."},
    "Jumper":{mode:"continuity",title:"Süreklilik (Ω)",probes:"Jumperın iki gerçek bağlantı ucunu PCB hattı veya şemadan doğrula; enerji kesildikten sonra sürekliliğini kontrol et.",explanation:"0 Ω jumper/bağlantı köprüsü düşük dirençli olabilir. Devre içi paralel yollar nedeniyle kesin sağlamlık eşiği verilemez."},
    "Bilinmiyor":{mode:"resistance",title:"Önce parça türünü belirle",probes:"Parça üzerindeki kodu incele, kılıf/bağlantı türünü ve datasheeti doğrula.",explanation:"Türü belirsiz eleman için sayısal ölçüm eşiği uydurulmaz."}
  });
  const MARKING_NOTE="Kodun parça türüne ve üretici işaretleme sistemine uygun olduğunu teknisyen doğrulamalıdır.";
  function prettyOhms(value){
    if(!Number.isFinite(value)||value<0)throw Error("Geçersiz Ω");
    const units=[[1e9,"GΩ"],[1e6,"MΩ"],[1e3,"kΩ"],[1,"Ω"]];
    for(const [factor,unit] of units)if(value>=factor||factor===1)
      return (Number((value/factor).toPrecision(7))).toLocaleString("tr-TR",{maximumFractionDigits:6})+" "+unit;
  }
  function bands(colors){
    if(!Array.isArray(colors)||![4,5].includes(colors.length))return null;
    const key=colors.map(x=>String(x).trim().toLocaleLowerCase("tr-TR")
      .replaceAll("ı","i").replaceAll("ş","s").replaceAll("ğ","g")
      .replaceAll("ü","u").replaceAll("ö","o").replaceAll("ç","c"));
    const significant=key.length-2;
    if(key.slice(0,significant).some(k=>!(k in DIGITS)) ||
        !(key[significant] in MULTIPLIER) || !(key[significant+1] in TOLERANCE))return null;
    let n=0;for(const k of key.slice(0,significant))n=n*10+DIGITS[k];
    const ohms=n*Math.pow(10,MULTIPLIER[key[significant]]);
    if(ohms<=0||!Number.isFinite(ohms))return null;
    const tolerance=TOLERANCE[key[significant+1]];
    return {kind:"nominal_marking",label:"Renk kodundan hesaplandı (onay bekler)",
      nominal_ohm:ohms,tolerance_percent:tolerance,minimum_ohm:ohms*(1-tolerance/100),
      maximum_ohm:ohms*(1+tolerance/100),
      display:prettyOhms(ohms)+" ±%"+tolerance+" · nominal tolerans "+prettyOhms(ohms*(1-tolerance/100))+" – "+prettyOhms(ohms*(1+tolerance/100)),
      caution:"Sadece doğru okunan bant kodu ve devreden ayrılmış direnç nominali için. "+MARKING_NOTE};
  }
  function smdResistor(marking){
    if(typeof marking!=="string")return null;
    const text=marking.trim().toUpperCase().replace(/\s/g,"");
    let ohms=null;
    if(/^(?:0{3}|0{4}|0R0|R00|00R)$/.test(text))ohms=0;
    else if(/^\d{2,3}R\d{1,2}$/.test(text)||/^\d{1,2}R\d{1,3}$/.test(text)||/^R\d{1,3}$/.test(text)){
      const decimal=text.replace("R",".");
      if(/^\d*\.?\d+$/.test(decimal))ohms=Number(decimal);
    }else if(/^\d{3}$/.test(text)){
      const significant=Number(text.slice(0,2)),power=Number(text[2]);
      ohms=significant*Math.pow(10,power);
    }else if(/^\d{4}$/.test(text)){
      const significant=Number(text.slice(0,3)),power=Number(text[3]);
      ohms=significant*Math.pow(10,power);
    }
    if(ohms===null||!Number.isFinite(ohms)||ohms<0||ohms>1e12)return null;
    return {kind:"nominal_marking",label:"Direnç işaret kodu (doğrula)",nominal_ohm:ohms,
      display:prettyOhms(ohms)+" nominal (tolerans bilinmiyor)",
      caution:"SMD/Trimpot direncinde standart kod sistemi kullanıldığı teyit edilmelidir. EIA-96 ve üretici özel kodları desteklenmez. Kod toleransı veya sağlamlığı göstermez."};
  }
  function capacitorMarking(marking){
    if(typeof marking!=="string")return null;
    const text=marking.trim().replaceAll(",",".");
    const numeric=text.match(/(\d+(?:\.\d+)?)\s*([unpµμ])\s*f\b/i);
    let pf;
    if(numeric){
      const scale={u:1e6,n:1e3,p:1,"µ":1e6,"μ":1e6};
      pf=Number(numeric[1])*scale[numeric[2].toLowerCase()];
    }else if(/^\d{3}$/.test(text)){
      pf=Number(text.slice(0,2))*Math.pow(10,Number(text[2]));
    }
    if(!Number.isFinite(pf)||pf<=0||pf>1e15)return null;
    const rating=text.match(/(\d+(?:\.\d+)?)\s*v\b/i);
    const value=pf>=1e6?(pf/1e6)+" µF":pf>=1e3?(pf/1e3)+" nF":pf+" pF";
    return {kind:"nominal_marking",label:"Kapasitör üzerinde yazan nominal kod",nominal_pf:pf,
      display:value+" nominal; tolerans bilinmiyor"+(rating?" · "+rating[1]+" V dayanım değeri":""),
      caution:"Bu koda ait üretici işaretlemesi doğrulanmalı. V yazısı karttaki beklenen voltaj değildir. Tolerans, ESR, sıcaklık ve devre koşulları bilinmeden ölçüm aralığı belirlenemez."};
  }
  function knowledge(label,marking="",colorBands=null){
    const guide=GUIDES[label]||GUIDES.Bilinmiyor;
    let decoded=null;
    if(label==="Direnç"||label==="Trimpot"){
      decoded=bands(colorBands)||smdResistor(marking);
    }else if(label==="Kondansatör"||label==="Elektrolitik Kondansatör"){
      decoded=capacitorMarking(marking);
    }
    return {label,mode:guide.mode,title:guide.title,probes:guide.probes,
      explanation:guide.explanation,typical_range:guide.typical_range||null,
      typical_unit:guide.unit||null,source:guide.source||null,kind:guide.kind||"no_universal_range",
      marking:decoded,verified:false};
  }
  return Object.freeze({LABELS,GUIDES,bands,smdResistor,capacitorMarking,knowledge,prettyOhms});
});
