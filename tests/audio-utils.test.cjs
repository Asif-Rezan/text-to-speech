const test = require('node:test');
const assert = require('node:assert/strict');
const {splitScript, readPcm, mergePcm} = require('../static/studio/audio-utils.js');

test('long Bangla scripts preserve words and punctuation in bounded sections', () => {
  const script = 'আজকের সকালে ঢাকার আকাশ পরিষ্কার।তুমি কেমন আছো? নতুন গল্প শুরু করি!\n'.repeat(100);
  const chunks = splitScript(script);
  assert.ok(script.length > 1000);
  assert.ok(chunks.length > 4);
  assert.ok(chunks.every(chunk => chunk.length > 0 && chunk.length <= 250));
  assert.equal(chunks.join('').replace(/\s/g, ''), script.replace(/\s/g, ''));
  assert.deepEqual(splitScript('   '), []);
  assert.equal(splitScript('ক'.repeat(20000)).join(''), 'ক'.repeat(20000));
});

test('merged WAV contains all sections in order and has the correct duration', async () => {
  const first = new Uint8Array([1, 0, 2, 0]), second = new Uint8Array([3, 0, 4, 0]);
  const {blob, seconds} = mergePcm([first, second]);
  const buffer = await blob.arrayBuffer();
  assert.equal(buffer.byteLength, 52);
  assert.equal(new DataView(buffer).getUint32(4, true), 44);
  assert.equal(new DataView(buffer).getUint32(40, true), 8);
  assert.equal(seconds, 8 / 48000);
  assert.deepEqual([...readPcm(buffer)], [1, 0, 2, 0, 3, 0, 4, 0]);
});

test('truncated or incompatible audio cannot become a playable-looking download', async () => {
  const buffer = await mergePcm([new Uint8Array([1, 0])]).blob.arrayBuffer();
  assert.throws(() => readPcm(buffer.slice(0, 45)), /Incomplete/);
  new DataView(buffer).setUint32(24, 48000, true);
  assert.throws(() => readPcm(buffer), /Incompatible/);
  assert.throws(() => readPcm(new ArrayBuffer(0)), /Invalid/);
});
