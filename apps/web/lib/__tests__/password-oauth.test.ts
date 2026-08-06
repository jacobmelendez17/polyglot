/** Password policy + OAuth helpers (frontend). */
import { checkPassword, passwordIsValid, PASSWORD_RULES } from "../password";
import { OAUTH_PROVIDERS, fetchOAuthProviders, oauthStartUrl } from "../oauth";

describe("password policy", () => {
  it("passes a strong password", () => {
    expect(passwordIsValid("Supersecret1!")).toBe(true);
    expect(Object.values(checkPassword("Supersecret1!")).every(Boolean)).toBe(true);
  });

  it("flags exactly what's missing", () => {
    const c = checkPassword("supersecret1");
    expect(c.uppercase).toBe(false);
    expect(c.special).toBe(false);
    expect(c.length).toBe(true);
    expect(passwordIsValid("supersecret1")).toBe(false);
  });

  it("space does not count as a special character", () => {
    expect(checkPassword("With Space1A").special).toBe(false);
  });

  it("has all five rules", () => {
    expect(PASSWORD_RULES.map((r) => r.key)).toEqual(
      ["length", "uppercase", "lowercase", "digit", "special"]);
  });
});

describe("oauth helpers", () => {
  it("lists the three providers", () => {
    expect(OAUTH_PROVIDERS.map((p) => p.key)).toEqual(["google", "discord", "github"]);
  });

  it("builds a start url", () => {
    expect(oauthStartUrl("google")).toContain("/api/v1/auth/oauth/google/start");
  });

  it("returns {} when the providers request fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("network"));
    expect(await fetchOAuthProviders()).toEqual({});
  });
});
