/**
 * Unit tests for the API client error handling. We mock fetch so no server is
 * needed; this verifies the client surfaces API errors and network failures
 * in the shape the UI expects.
 */
import { api, ApiClientError } from "../api";

describe("api client", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("returns tokens on successful login", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "a", refresh_token: "r" }),
    }) as jest.Mock;

    const tokens = await api.login("x@example.com", "password1");
    expect(tokens.access_token).toBe("a");
  });

  it("throws ApiClientError with the server message on 401", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { code: "invalid_credentials", message: "Invalid email or password." } }),
    }) as jest.Mock;

    await expect(api.login("x@example.com", "wrong")).rejects.toMatchObject({
      status: 401,
      code: "invalid_credentials",
    });
  });

  it("wraps network failures as a network_error", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("boom")) as jest.Mock;
    await expect(api.me("token")).rejects.toBeInstanceOf(ApiClientError);
    await expect(api.me("token")).rejects.toMatchObject({ code: "network_error" });
  });
});
