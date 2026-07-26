/**
 * The account/deck client. These are thin wrappers, so the tests pin the
 * request shapes (method, path, body) the backend expects rather than behaviour.
 */
import { account, decks } from "../account-api";

const okJson = (data: unknown) => ({
  ok: true,
  status: 200,
  json: async () => data,
});

describe("account client", () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ ok: true, message: "sent" }));
  });

  it("posts the email to forgot-password", async () => {
    await account.forgotPassword("a@b.com");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/auth/forgot-password");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ email: "a@b.com" });
  });

  it("posts token and new_password to reset-password", async () => {
    await account.resetPassword("tok", "newpass12");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/auth/reset-password");
    expect(JSON.parse(init.body)).toEqual({ token: "tok", new_password: "newpass12" });
  });

  it("posts the token to verify-email", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      okJson({ verified: true, already_verified: false }),
    );
    const r = await account.verifyEmail("tok");
    expect(r.verified).toBe(true);
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/auth/verify-email");
  });
});

describe("decks client", () => {
  it("lists decks", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson([{ type: "vocabulary", title: "vocabulary", description: "", count: 3 }]),
    );
    const list = await decks.list();
    expect(list[0].type).toBe("vocabulary");
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/decks");
  });

  it("passes pagination to the deck items endpoint", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ type: "vocabulary", total: 0, limit: 40, offset: 40, items: [] }),
    );
    await decks.items("vocabulary", 40, 40);
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/decks/vocabulary?limit=40&offset=40");
  });
});
