/** /llms.txt – Kurzfassung für KI-Assistenten (llmstxt.org), aus Konfiguration und Seitenliste. */
import type { APIRoute } from 'astro';
import { llmsTxt } from '../lib/llms';

export const GET: APIRoute = ({ site }) =>
  new Response(llmsTxt(site!.href.replace(/\/$/, '')), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
