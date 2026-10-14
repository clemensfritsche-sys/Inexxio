/** /llms-full.txt – alle indexierbaren Seiten im Wortlaut, für KI-Assistenten. */
import type { APIRoute } from 'astro';
import { llmsFullTxt } from '../lib/llms';

export const GET: APIRoute = ({ site }) =>
  new Response(llmsFullTxt(site!.href.replace(/\/$/, '')), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
