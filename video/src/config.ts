// Всё, что относится к конкретному боту. Остальной код ролика общий для демо-ботов.
export type Ev = {
  op: string;
  chat: number | null;
  id?: number;
  text?: string;
  button?: string;
};

export const BOT_TITLE = "Бритва — запись онлайн";
export const AVATAR = { letter: "Б", gradient: "linear-gradient(135deg,#8e7cf0,#4b3bb5)" };
export const INTRO = { title: "Онлайн-запись в барбершоп", subtitle: "Telegram-бот · свободные слоты · напоминания · админка" };
export const OUTRO = {
  title: "Что умеет бот",
  features: [
    "Запись в 4 клика: услуга → мастер → день → время",
    "Только свободные слоты с учётом длительности услуги",
    "Напоминание клиенту за 2 часа до визита",
    "Клиент сам отменяет запись — слот освобождается",
    "Уведомления и расписание с выручкой для админа",
  ],
  footer: "Ролик собран из реальных ответов бота · код: github.com/Slomi/BrBot",
};

export const CAPTION_RULES = (admin: number): { test: (e: Ev) => boolean; text: string }[] => [
  { test: (e) => e.op === "user" && e.text === "/start", text: "Клиент открывает бота барбершопа" },
  { test: (e) => e.op === "user" && !!e.text?.includes("Записаться"), text: "Запись в 4 клика: услуга → мастер → день → время" },
  { test: (e) => e.op === "click" && /^\d\d:\d\d$/.test(e.button ?? ""), text: "Показывает только свободное время" },
  { test: (e) => e.op === "user" && !!e.text?.startsWith("+7"), text: "Телефон — кнопкой или вручную" },
  { test: (e) => e.op === "bot" && e.chat === admin && !!e.text?.includes("Новая запись"), text: "Админ сразу видит новую запись" },
  { test: (e) => e.op === "clock", text: "Напоминание за 2 часа — меньше неявок" },
  { test: (e) => e.op === "user" && e.text === "/admin", text: "Расписание и выручка на день и неделю" },
  { test: (e) => e.op === "user" && !!e.text?.includes("Мои записи"), text: "Клиент сам отменяет запись — админ в курсе" },
];
