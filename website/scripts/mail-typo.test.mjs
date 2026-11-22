import { test } from 'node:test';
import assert from 'node:assert/strict';
import { suggest } from '../src/lib/mail-typo.mjs';

test('ein Tippfehler bei einem grossen Anbieter wird vorgeschlagen', () => {
  assert.equal(suggest('clemens.fritsche@gmai.com'), 'clemens.fritsche@gmail.com');
  assert.equal(suggest('lea@gmial.com'), 'lea@gmail.com');
  assert.equal(suggest('lea@bluewin.cg'), 'lea@bluewin.ch');
  assert.equal(suggest('lea@hotmial.com'), 'lea@hotmail.com');
  assert.equal(suggest('Lea@GMAIL.CON'), 'Lea@gmail.com');
});

test('richtige und fremde Adressen bleiben, wie sie sind', () => {
  for (const ok of ['lea@gmail.com', 'lea@gmx.ch', 'info@inexxio.com', 'max@web.ch', 'a@hs-steiner.ch', 'kein-at', 'x@']) {
    assert.equal(suggest(ok), null, ok);
  }
});
