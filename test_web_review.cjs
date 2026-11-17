// Offline review tests; no browser, credentials, external image, or model required.
"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const review=require("./web_review.js");

const box={id:1,label:"Direnç",confirmed:true,bbox_xyxy_pixels:[10,20,30,35]};
const args=()=>({
  boardId:"kart_001",
  image:"board front.jpg",
  width:100,height:80,
  regions:[box],
  completedReview:true
});
test("exports a pipeline-compatible reviewed annotation",()=>{
  const result=review.trainingAnnotation(args());
  assert.equal(result.coordinate_system,"xyxy_normalized");
  assert.equal(result.technician_verified,true);
  assert.equal(result.board_id,"kart_001");
  assert.equal(result.image,"board front.jpg");
  assert.equal(result.regions.length,1);
  assert.deepEqual(result.regions[0].bbox_xyxy_normalized,[.1,.25,.3,.4375]);
});

test("rejects unverified labels, unknown parts and incomplete review",()=>{
  assert.throws(()=>review.trainingAnnotation({...args(),completedReview:false}),/görünür parçaları/);
  assert.throws(()=>review.trainingAnnotation({...args(),regions:[{...box,confirmed:false}]}),/Bütün işaretleri/);
  assert.throws(()=>review.trainingAnnotation({...args(),regions:[{...box,label:"Bilinmiyor"}]}),/Bütün işaretleri/);
  assert.throws(()=>review.trainingAnnotation({...args(),regions:[]}),/en az bir/);
});

test("rejects invalid coordinates and traversal in photo names",()=>{
  assert.throws(()=>review.trainingAnnotation({...args(),regions:[{...box,bbox_xyxy_pixels:[-1,0,10,10]}]}),/sınırları/);
  assert.throws(()=>review.trainingAnnotation({...args(),image:"../../private.jpg"}),/Fotoğraf adı/);
  assert.throws(()=>review.trainingAnnotation({...args(),boardId:""}),/Kart kimliği/);
});

const measurement=()=>({
  reading:"4,7",mode:"resistance",circuitState:"out_of_circuit",
  referenceMode:"resistance",referenceState:"out_of_circuit",
  minimum:"4.5",maximum:"5.0",partNumber:"R101 - 4R7",
  sourceUrl:"https://manufacturer.example.com/datasheet.pdf",
  conditions:"25C, offline, 2wire",technicianVerified:true
});

test("a measurement can be within a verified, matching reference without claiming health",()=>{
  const x=review.evaluateReference(measurement());
  assert.equal(x.code,"within");
  assert.match(x.message,/kanıtlamaz/);
  assert.equal(review.evaluateReference({...measurement(),reading:"6.1"}).code,"outside");
});
test("in-circuit measurements do not yield health comparison",()=>{
  const x=review.evaluateReference({...measurement(),circuitState:"in_circuit",referenceState:"in_circuit"});
  assert.equal(x.code,"needs_review");
});
test("rejects mismatched modes, conditions or missing evidence",()=>{
  assert.throws(()=>review.evaluateReference({...measurement(),referenceMode:"diode"}),/aynı olmalı/);
  assert.throws(()=>review.evaluateReference({...measurement(),referenceState:"in_circuit"}),/aynı olmalı/);
  assert.throws(()=>review.evaluateReference({...measurement(),sourceUrl:"http://manufacturer.example.com"}),/HTTPS/);
  assert.throws(()=>review.evaluateReference({...measurement(),technicianVerified:false}),/teknisyen onayı/);
  assert.throws(()=>review.evaluateReference({...measurement(),minimum:"6",maximum:"2"}),/geçerli/);
});

test("Turkish decimal, zero and invalid entries",()=>{
  assert.equal(review.parseDecimal("0"),0);
  assert.equal(review.parseDecimal("4,72"),4.72);
  assert.equal(review.parseDecimal("-1"),null);
  assert.equal(review.parseDecimal("NaN"),null);
  assert.equal(review.parseDecimal("1e4"),null);
});
