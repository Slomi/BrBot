// Превращает запись реального диалога с ботом (data/script.json) в раскадровку.
import script from "./data/script.json";
import { CAPTION_RULES, Ev as ConfigEv } from "./config";

export const FPS = 30;
export const INTRO = 3 * FPS;
export const OUTRO = 5 * FPS;

type Markup = { inline?: string[][]; reply?: string[][]; remove?: boolean } | null;
type Ev = ConfigEv & { markup?: Markup; reply_to?: number | null };

export type Edit = { at: number; text: string; inline?: string[][] };
export type Item = {
  id: number;
  chat: number;
  out: boolean; // сообщение пользователя (справа, синее)
  start: number;
  text: string;
  html: boolean;
  inline?: string[][];
  replyTo?: string;
  edits: Edit[];
};
export type Span = { from: number; to: number };
export type Press = { at: number; msgId: number | null; button: string }; // msgId=null — кнопка reply-клавиатуры
export type Caption = { at: number; text: string };
export type Toast = { at: number; text: string };
export type Clock = Span & { text: string };

export const CLIENT = script.client;
export const ADMIN = script.admin;

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const plain = (s: string) => s.replace(/<[^>]+>/g, "");
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export type Timeline = {
  items: Item[];
  typing: Record<number, Span[]>; // «печатает…» в шапке чата
  inputs: Record<number, (Span & { text: string })[]>; // набор текста в поле ввода
  replyKb: Record<number, { at: number; rows: string[][] | null }[]>;
  presses: Record<number, Press[]>;
  toasts: Record<number, Toast[]>; // всплывашки после нажатия inline-кнопки
  clocks: Clock[]; // заставка «прошло время»
  captions: Caption[];
  duration: number;
};

export const buildTimeline = (): Timeline => {
  const events = script.events as Ev[];
  const rules = CAPTION_RULES(ADMIN);
  const tl: Timeline = {
    items: [],
    typing: { [CLIENT]: [], [ADMIN]: [] },
    inputs: { [CLIENT]: [], [ADMIN]: [] },
    replyKb: { [CLIENT]: [], [ADMIN]: [] },
    presses: { [CLIENT]: [], [ADMIN]: [] },
    toasts: { [CLIENT]: [], [ADMIN]: [] },
    clocks: [],
    captions: [],
    duration: 0,
  };
  const byId = new Map<string, Item>();
  const usedCaptions = new Set<number>();
  let t = INTRO + 10;
  let lastUserChat = CLIENT;

  events.forEach((e, idx) => {
    rules.forEach((r, i) => {
      if (!usedCaptions.has(i) && r.test(e)) {
        usedCaptions.add(i);
        tl.captions.push({ at: t, text: r.text });
      }
    });
    const next = events[idx + 1];

    if (e.op === "user" && e.chat !== null && e.text) {
      const chat = e.chat;
      const kbNow = [...tl.replyKb[chat]].reverse().find((k) => k.at <= t)?.rows ?? null;
      const isKbButton = !!kbNow?.some((row) => row.includes(e.text!));
      if (isKbButton) {
        tl.presses[chat].push({ at: t, msgId: null, button: e.text });
        t += 14;
      } else {
        const dur = clamp(Math.round(e.text.length * 1.1), 14, 70);
        tl.inputs[chat].push({ from: t, to: t + dur, text: e.text });
        t += dur + 4;
      }
      const replied = e.reply_to ? byId.get(`${chat}:${e.reply_to}`) : undefined;
      const item: Item = {
        id: e.id!, chat, out: true, start: t, text: escapeHtml(e.text), html: true, edits: [],
        replyTo: replied ? plain(replied.text).split("\n")[0] : undefined,
      };
      tl.items.push(item);
      byId.set(`${chat}:${e.id}`, item);
      lastUserChat = chat;
      t += 10;
    } else if (e.op === "click" && e.chat !== null) {
      tl.presses[e.chat].push({ at: t, msgId: e.id!, button: e.button! });
      lastUserChat = e.chat;
      t += 16;
    } else if (e.op === "toast" && e.text) {
      tl.toasts[lastUserChat].push({ at: t, text: e.text });
    } else if (e.op === "clock" && e.text) {
      t += 10;
      tl.clocks.push({ from: t, to: t + 50, text: e.text });
      t += 56;
    } else if (e.op === "bot" && e.chat !== null && e.text !== undefined) {
      const chat = e.chat;
      const len = plain(e.text).length;
      if (chat === lastUserChat) {
        const typing = len > 140 ? 40 : 14;
        tl.typing[chat].push({ from: t, to: t + typing });
        t += typing;
      } else {
        t += 8; // уведомление в другой чат приходит почти сразу
      }
      const item: Item = {
        id: e.id!, chat, out: false, start: t, text: e.text, html: true, edits: [],
        inline: e.markup?.inline,
      };
      tl.items.push(item);
      byId.set(`${chat}:${e.id}`, item);
      if (e.markup?.reply) tl.replyKb[chat].push({ at: t, rows: e.markup.reply });
      if (e.markup?.remove) tl.replyKb[chat].push({ at: t, rows: null });
      // пауза на чтение; если следом сразу ещё сообщение бота — короче
      const burst = next && (next.op === "bot" || next.op === "toast");
      t += burst ? 12 : clamp(Math.round(len * 0.55), 30, 135);
    } else if (e.op === "edit" && e.chat !== null && e.text !== undefined) {
      const item = byId.get(`${e.chat}:${e.id}`);
      if (item) item.edits.push({ at: t, text: e.text, inline: e.markup?.inline });
      const len = plain(e.text).length;
      // если дальше клик — даём рассмотреть кнопки (сетка слотов и т.п.), иначе — прочитать текст
      const buttons = (e.markup?.inline ?? []).flat().length;
      const quick = next && next.op === "click";
      t += quick ? clamp(20 + buttons * 3, 30, 80) : clamp(Math.round(len * 0.55), 75, 150);
    }
  });

  tl.duration = t + 20 + OUTRO;
  return tl;
};
