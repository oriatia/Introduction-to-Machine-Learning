export type Role = "user" | "advisor" | "admin";

export type Me = {
  id: string;
  role: Role;
  phone_masked: string;
};

export const SESSION_COOKIE = "hazar_session";

/** Wrap left-to-right content (phone numbers, codes) in Unicode isolates so it renders correctly inside Hebrew text. */
export function ltr(text: string): string {
  return `⁦${text}⁩`;
}
