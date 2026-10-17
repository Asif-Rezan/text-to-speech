(() => {
  function splitScript(script, limit = 250) {
    const units = script.trim().match(/[^।!?\n]+[।!?]?|[।!?]/gu) || [];
    const chunks = [];
    let current = '';
    for (let unit of units.map(unit => unit.trim()).filter(Boolean)) {
      while (unit.length > limit) {
        if (current) { chunks.push(current); current = ''; }
        const space = unit.lastIndexOf(' ', limit);
        const end = space > limit / 2 ? space : limit;
        chunks.push(unit.slice(0, end).trim());
        unit = unit.slice(end).trim();
      }
      if (!unit) continue;
      if (current && current.length + unit.length + 1 > limit) {
        chunks.push(current); current = '';
      }
      current = current ? `${current} ${unit}` : unit;
    }
    if (current) chunks.push(current);
    return chunks;
  }

  function readPcm(buffer) {
    const view = new DataView(buffer);
    const tag = offset => String.fromCharCode(...new Uint8Array(buffer, offset, 4));
    if (buffer.byteLength < 44 || tag(0) !== 'RIFF' || tag(8) !== 'WAVE') throw new Error('Invalid WAV section.');
    let pcm, format;
    for (let offset = 12; offset + 8 <= buffer.byteLength;) {
      const size = view.getUint32(offset + 4, true), start = offset + 8;
      if (start + size > buffer.byteLength) throw new Error('Incomplete WAV section.');
      if (tag(offset) === 'fmt ' && size >= 16) {
        format = [view.getUint16(start, true), view.getUint16(start + 2, true),
          view.getUint32(start + 4, true), view.getUint16(start + 14, true)];
      }
      if (tag(offset) === 'data') pcm = new Uint8Array(buffer, start, size);
      offset = start + size + (size % 2);
    }
    if (!format || format.join(',') !== '1,1,24000,16' || !pcm?.length || pcm.length % 2) {
      throw new Error('Incompatible WAV section.');
    }
    return pcm;
  }

  function mergePcm(parts) {
    const size = parts.reduce((total, part) => total + part.byteLength, 0);
    const header = new ArrayBuffer(44), view = new DataView(header);
    const writeTag = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
    writeTag(0, 'RIFF'); view.setUint32(4, size + 36, true); writeTag(8, 'WAVE');
    writeTag(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, 24000, true); view.setUint32(28, 48000, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    writeTag(36, 'data'); view.setUint32(40, size, true);
    return {blob: new Blob([header, ...parts], {type: 'audio/wav'}), seconds: size / 48000};
  }

  const helpers = {splitScript, readPcm, mergePcm};
  if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
  else window.NeuralVoiceAudio = helpers;
})();
