/** /robots.txt – je nach Modus; der Inhalt steht in src/lib/robots.mjs. */
import type { APIRoute } from 'astro';
import { robotsTxt } from '../lib/robots.mjs';
import { siteMode } from '../lib/text.mjs';

export const GET: APIRoute = ({ site }) =>
  new Response(robotsTxt(siteMode(), site!.href.replace(/\/$/, '')), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
