// Die Beschränkung des Website-Stylesheets auf Kopf und Fuss im Konto/ERP (export-shell.mjs):
// eine Regel, die durchrutscht, träfe die ganze ERP-Oberfläche.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scope } from './shell-scope.mjs';

test('gewöhnliche Regeln gelten nur in der Hülle', () => {
  assert.equal(scope('.btn--primary'), '.ix-shell .btn--primary');
  assert.equal(scope('a'), '.ix-shell a');
  assert.equal(scope('*'), '.ix-shell *');
  assert.equal(scope('h1, h2'.split(',')[1]), '.ix-shell h2');
});

test(':root und body werden zur Hülle (Tokens, Schrift)', () => {
  assert.equal(scope(':root'), '.ix-shell');
  assert.equal(scope('body'), '.ix-shell');
  assert.equal(scope('body .x'), '.ix-shell .x');
});

test('Regeln am <html> behalten ihr html vorne', () => {
  assert.equal(scope("html[data-account] [data-acct='login']"), "html[data-account] .ix-shell [data-acct='login']");
  assert.equal(scope("html:not([data-account='staff']) [data-acct='staff']"), "html:not([data-account='staff']) .ix-shell [data-acct='staff']");
  assert.equal(scope('html.menu-open'), 'html.menu-open');
  assert.equal(scope('.js .site-header.is-scrolled'), 'html.js .ix-shell .site-header.is-scrolled');
  assert.equal(scope('html:not(.js) .dd:focus-within .dd__panel'), 'html:not(.js) .ix-shell .dd:focus-within .dd__panel');
});
