import { beforeEach, describe, expect, it } from "vitest";
import { clearSession, isSessionValid, readSession, saveSession } from "@/lib/auth";

describe("session storage", () => {
  beforeEach(() => {
    clearSession();
  });

  it("saveSession + readSession round-trip", () => {
    saveSession({
      accessToken: "abc",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: 1_234_567_890_000,
    });
    const s = readSession();
    expect(s).toEqual({
      accessToken: "abc",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: 1_234_567_890_000,
    });
  });

  it("readSession devuelve null si falta algún campo", () => {
    localStorage.setItem("argos.access_token", "abc");
    expect(readSession()).toBeNull();
  });

  it("isSessionValid detecta expiración", () => {
    expect(isSessionValid(null)).toBe(false);
    expect(
      isSessionValid({ accessToken: "a", workspaceId: "R", role: "ceo", expiresAt: Date.now() - 1 })
    ).toBe(false);
    expect(
      isSessionValid({
        accessToken: "a",
        workspaceId: "R",
        role: "ceo",
        expiresAt: Date.now() + 60_000,
      })
    ).toBe(true);
  });

  it("clearSession elimina todos los campos", () => {
    saveSession({ accessToken: "a", workspaceId: "R", role: "ceo", expiresAt: 1 });
    clearSession();
    expect(readSession()).toBeNull();
  });
});
