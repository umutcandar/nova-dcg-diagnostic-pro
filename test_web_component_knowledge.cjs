"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const kb=require("./web_component_knowledge.js");

test("knowledge table covers all 24 training classes and never claims health",()=>{
  assert.equal(kb.LABELS.length,24);
  for(const label of kb.LABELS){
    const item=kb.knowledge(label);
    assert.ok(item.mode);
    assert.equal(item.verified,false);
  }
  assert.equal(kb.knowledge("Trimpot").mode,"resistance");
  assert.equal(kb.knowledge("Batarya").mode,"none");
  assert.equal(kb.knowledge("Soğutucu").mode,"none");
  assert.equal(kb.knowledge("Sigorta").mode,"continuity");
  assert.match(kb.knowledge("Trimpot").explanation,/sürgü|Sürgü/i);
});

test("Fluke's common silicon diode range is clearly typical, not a universal pass criterion",()=>{
  const guide=kb.knowledge("Diyot");
  assert.deepEqual(guide.typical_range,[0.5,0.8]);
  assert.equal(guide.kind,"typical");
  assert.match(guide.explanation,/Schottky/);
  assert.equal(kb.knowledge("LED").typical_range,null);
  assert.equal(kb.knowledge("MOSFET").typical_range,null);
});

test("four-band resistor brown black red gold is 1k +/-5 percent",()=>{
  const x=kb.bands(["kahverengi","siyah","kirmizi","altin"]);
  assert.equal(x.nominal_ohm,1000);
  assert.equal(x.tolerance_percent,5);
  assert.equal(x.minimum_ohm,950);
  assert.equal(x.maximum_ohm,1050);
  assert.match(x.caution,/devreden ayrılmış/);
});

test("five-band precision resistor code and missing band validation",()=>{
  const x=kb.bands(["kahverengi","siyah","siyah","kirmizi","kahverengi"]);
  assert.equal(x.nominal_ohm,10000);
  assert.equal(x.tolerance_percent,1);
  assert.equal(kb.bands(["kirmizi","siyah","gri"]),null);
  assert.equal(kb.bands(["altin","siyah","kirmizi","altin"]),null);
});

test("resistor marks are nominal only, not assumed datasheet tolerance",()=>{
  assert.equal(kb.smdResistor("103").nominal_ohm,10000);
  assert.equal(kb.smdResistor("1002").nominal_ohm,10000);
  assert.equal(kb.smdResistor("4R7").nominal_ohm,4.7);
  assert.equal(kb.smdResistor("R47").nominal_ohm,0.47);
  assert.equal(kb.smdResistor("000").nominal_ohm,0);
  assert.equal(kb.smdResistor("01C"),null);
  assert.equal(kb.smdResistor("IC103"),null);
  assert.equal(kb.smdResistor(""),null);
  assert.equal(kb.knowledge("Entegre","103").marking,null);
});

test("trimpot nominal from conventional mark is not a fixed wiper reading",()=>{
  const x=kb.knowledge("Trimpot","103");
  assert.equal(x.marking.nominal_ohm,10000);
  assert.match(x.explanation,/ayar|ayara/);
  assert.equal(x.marking.tolerance_percent,undefined);
});

test("marked capacitor type and rated voltage are not mistaken for circuit voltage",()=>{
  const x=kb.capacitorMarking("100uF 25V");
  assert.equal(x.nominal_pf,100000000);
  assert.match(x.display,/25 V dayanım/);
  assert.match(x.caution,/beklenen voltaj değildir/);
  assert.equal(kb.capacitorMarking("104").nominal_pf,100000);
  assert.equal(kb.capacitorMarking("Bilinmiyor"),null);
  assert.equal(kb.knowledge("Direnç","100uF 25V").marking,null);
});
