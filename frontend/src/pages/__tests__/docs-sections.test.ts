import { describe, it, expect } from "vitest";
import {
  SECTIONS,
  SIDEBAR_GROUPS,
  type DocSection,
  type DocEndpoint,
  type EndpointParam,
  type SidebarGroup,
} from "../docs-sections";

// ── Type-shape guard helpers ──────────────────────────────────────────────────
function isDocSection(obj: unknown): obj is DocSection {
  if (typeof obj !== "object" || obj === null) return false;
  const s = obj as Record<string, unknown>;
  return (
    typeof s.id === "string" &&
    typeof s.title === "string" &&
    typeof s.description === "string" &&
    Array.isArray(s.code)
  );
}

function isDocEndpoint(obj: unknown): obj is DocEndpoint {
  if (typeof obj !== "object" || obj === null) return false;
  const e = obj as Record<string, unknown>;
  return typeof e.method === "string" && typeof e.path === "string" && typeof e.description === "string";
}

function isEndpointParam(obj: unknown): obj is EndpointParam {
  if (typeof obj !== "object" || obj === null) return false;
  const p = obj as Record<string, unknown>;
  return (
    typeof p.name === "string" &&
    typeof p.type === "string" &&
    typeof p.required === "boolean" &&
    typeof p.desc === "string"
  );
}

// ── SECTIONS ──────────────────────────────────────────────────────────────────
describe("SECTIONS", () => {
  it("is a non-empty array", () => {
    expect(Array.isArray(SECTIONS)).toBe(true);
    expect(SECTIONS.length).toBeGreaterThan(0);
  });

  it("every section satisfies the DocSection shape", () => {
    for (const section of SECTIONS) {
      expect(isDocSection(section)).toBe(true);
    }
  });

  it("every section has a non-empty string id", () => {
    for (const section of SECTIONS) {
      expect(typeof section.id).toBe("string");
      expect(section.id.length).toBeGreaterThan(0);
    }
  });

  it("every section has a non-empty title", () => {
    for (const section of SECTIONS) {
      expect(section.title.length).toBeGreaterThan(0);
    }
  });

  it("every section has a non-empty description", () => {
    for (const section of SECTIONS) {
      expect(section.description.length).toBeGreaterThan(0);
    }
  });

  it("every section has at least one code example", () => {
    for (const section of SECTIONS) {
      expect(Array.isArray(section.code)).toBe(true);
      expect(section.code.length).toBeGreaterThan(0);
    }
  });

  it("every code example has a language and non-empty code string", () => {
    for (const section of SECTIONS) {
      for (const example of section.code) {
        expect(typeof example.language).toBe("string");
        expect(example.language.length).toBeGreaterThan(0);
        expect(typeof example.code).toBe("string");
        expect(example.code.length).toBeGreaterThan(0);
      }
    }
  });

  it("all section ids are unique", () => {
    const ids = SECTIONS.map((s) => s.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });

  it("all section titles are unique", () => {
    const titles = SECTIONS.map((s) => s.title);
    const uniqueTitles = new Set(titles);
    expect(uniqueTitles.size).toBe(titles.length);
  });

  it("contains the 'getting-started' section", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started");
    expect(section).toBeDefined();
    expect(section!.title).toBe("Getting Started");
  });

  it("contains the 'authentication' section", () => {
    const section = SECTIONS.find((s) => s.id === "authentication");
    expect(section).toBeDefined();
    expect(section!.title).toBe("Authentication");
  });

  it("getting-started section has expected endpoints", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started")!;
    expect(Array.isArray(section.endpoints)).toBe(true);
    expect(section.endpoints!.length).toBeGreaterThan(0);

    const healthEndpoint = section.endpoints!.find((e) => e.path === "/health");
    expect(healthEndpoint).toBeDefined();
    expect(healthEndpoint!.method).toBe("GET");
    expect(healthEndpoint!.auth).toBe(false);
  });

  it("getting-started section has a /health/cdn endpoint", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started")!;
    const cdnEndpoint = section.endpoints!.find((e) => e.path === "/health/cdn");
    expect(cdnEndpoint).toBeDefined();
    expect(cdnEndpoint!.method).toBe("GET");
    expect(cdnEndpoint!.auth).toBe(false);
  });

  it("authentication section has the /agents/register endpoint", () => {
    const section = SECTIONS.find((s) => s.id === "authentication")!;
    expect(Array.isArray(section.endpoints)).toBe(true);
    const registerEndpoint = section.endpoints!.find((e) => e.path === "/agents/register");
    expect(registerEndpoint).toBeDefined();
    expect(registerEndpoint!.method).toBe("POST");
    expect(registerEndpoint!.auth).toBe(false);
  });

  it("authentication /agents/register endpoint has required params", () => {
    const section = SECTIONS.find((s) => s.id === "authentication")!;
    const registerEndpoint = section.endpoints!.find((e) => e.path === "/agents/register")!;
    expect(Array.isArray(registerEndpoint.params)).toBe(true);

    const params = registerEndpoint.params!;
    const nameParam = params.find((p) => p.name === "name");
    expect(nameParam).toBeDefined();
    expect(nameParam!.required).toBe(true);

    const agentTypeParam = params.find((p) => p.name === "agent_type");
    expect(agentTypeParam).toBeDefined();
    expect(agentTypeParam!.required).toBe(true);

    const publicKeyParam = params.find((p) => p.name === "public_key");
    expect(publicKeyParam).toBeDefined();
    expect(publicKeyParam!.required).toBe(true);
  });

  it("authentication /agents/register endpoint has optional params", () => {
    const section = SECTIONS.find((s) => s.id === "authentication")!;
    const registerEndpoint = section.endpoints!.find((e) => e.path === "/agents/register")!;
    const params = registerEndpoint.params!;

    const capabilitiesParam = params.find((p) => p.name === "capabilities");
    expect(capabilitiesParam).toBeDefined();
    expect(capabilitiesParam!.required).toBe(false);

    const walletParam = params.find((p) => p.name === "wallet_address");
    expect(walletParam).toBeDefined();
    expect(walletParam!.required).toBe(false);
  });

  it("all endpoints that have params satisfy the EndpointParam shape", () => {
    for (const section of SECTIONS) {
      if (!section.endpoints) continue;
      for (const endpoint of section.endpoints) {
        expect(isDocEndpoint(endpoint)).toBe(true);
        if (endpoint.params) {
          for (const param of endpoint.params) {
            expect(isEndpointParam(param)).toBe(true);
          }
        }
      }
    }
  });

  it("all endpoints have a response string when response is defined", () => {
    for (const section of SECTIONS) {
      if (!section.endpoints) continue;
      for (const endpoint of section.endpoints) {
        if (endpoint.response !== undefined) {
          expect(typeof endpoint.response).toBe("string");
          expect(endpoint.response.length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("details, when present, is a non-empty string array", () => {
    for (const section of SECTIONS) {
      if (section.details !== undefined) {
        expect(Array.isArray(section.details)).toBe(true);
        expect(section.details.length).toBeGreaterThan(0);
        for (const detail of section.details) {
          expect(typeof detail).toBe("string");
          expect(detail.length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("getting-started section details include rate limiting info", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started")!;
    expect(Array.isArray(section.details)).toBe(true);
    const rateDetail = section.details!.find((d) => d.toLowerCase().includes("rate limit"));
    expect(rateDetail).toBeDefined();
  });

  it("getting-started code examples include Python, JavaScript, and cURL languages", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started")!;
    const languages = section.code.map((c) => c.language);
    expect(languages).toContain("Python");
    expect(languages).toContain("JavaScript");
    expect(languages).toContain("cURL");
  });

  it("health endpoint response is valid JSON", () => {
    const section = SECTIONS.find((s) => s.id === "getting-started")!;
    const healthEndpoint = section.endpoints!.find((e) => e.path === "/health")!;
    expect(() => JSON.parse(healthEndpoint.response!)).not.toThrow();
    const parsed = JSON.parse(healthEndpoint.response!);
    expect(parsed).toHaveProperty("status");
    expect(parsed).toHaveProperty("version");
  });

  it("agent register endpoint response contains jwt_token field", () => {
    const section = SECTIONS.find((s) => s.id === "authentication")!;
    const endpoint = section.endpoints!.find((e) => e.path === "/agents/register")!;
    const parsed = JSON.parse(endpoint.response!);
    expect(parsed).toHaveProperty("jwt_token");
  });
});

// ── SIDEBAR_GROUPS ────────────────────────────────────────────────────────────
describe("SIDEBAR_GROUPS", () => {
  it("is a non-empty array", () => {
    expect(Array.isArray(SIDEBAR_GROUPS)).toBe(true);
    expect(SIDEBAR_GROUPS.length).toBeGreaterThan(0);
  });

  it("every group satisfies the SidebarGroup shape", () => {
    for (const group of SIDEBAR_GROUPS) {
      expect(typeof group.label).toBe("string");
      expect(group.label.length).toBeGreaterThan(0);
      expect(Array.isArray(group.sectionIds)).toBe(true);
      expect(group.sectionIds.length).toBeGreaterThan(0);
    }
  });

  it("all group labels are unique", () => {
    const labels = SIDEBAR_GROUPS.map((g) => g.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("contains a 'Getting Started' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Getting Started");
    expect(group).toBeDefined();
    expect(group!.sectionIds).toContain("getting-started");
    expect(group!.sectionIds).toContain("authentication");
  });

  it("contains a 'Marketplace' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Marketplace");
    expect(group).toBeDefined();
    expect(group!.sectionIds.length).toBeGreaterThan(0);
  });

  it("contains an 'Intelligence' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Intelligence");
    expect(group).toBeDefined();
  });

  it("contains a 'Billing' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Billing");
    expect(group).toBeDefined();
  });

  it("contains a 'Trust' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Trust");
    expect(group).toBeDefined();
  });

  it("contains an 'Integrations' group", () => {
    const group = SIDEBAR_GROUPS.find((g) => g.label === "Integrations");
    expect(group).toBeDefined();
  });

  it("every sectionId in every group corresponds to a real SECTION", () => {
    const sectionIds = new Set(SECTIONS.map((s) => s.id));
    for (const group of SIDEBAR_GROUPS) {
      for (const id of group.sectionIds) {
        expect(sectionIds.has(id)).toBe(true);
      }
    }
  });

  it("the union of all group sectionIds covers all SECTIONS", () => {
    const coveredIds = new Set(SIDEBAR_GROUPS.flatMap((g) => g.sectionIds));
    for (const section of SECTIONS) {
      expect(coveredIds.has(section.id)).toBe(true);
    }
  });

  it("no sectionId appears in more than one group", () => {
    const allIds = SIDEBAR_GROUPS.flatMap((g) => g.sectionIds);
    const uniqueIds = new Set(allIds);
    expect(uniqueIds.size).toBe(allIds.length);
  });
});

// ── Exported TypeScript interfaces (structural tests) ─────────────────────────
describe("Type shape contracts", () => {
  it("EndpointParam fields are of the correct types", () => {
    const param: EndpointParam = {
      name: "test_param",
      type: "string",
      required: true,
      desc: "A test parameter",
    };
    expect(typeof param.name).toBe("string");
    expect(typeof param.type).toBe("string");
    expect(typeof param.required).toBe("boolean");
    expect(typeof param.desc).toBe("string");
  });

  it("DocEndpoint can be constructed with only mandatory fields", () => {
    const endpoint: DocEndpoint = {
      method: "GET",
      path: "/test",
      description: "Test endpoint",
    };
    expect(endpoint.method).toBe("GET");
    expect(endpoint.path).toBe("/test");
    expect(endpoint.auth).toBeUndefined();
    expect(endpoint.params).toBeUndefined();
    expect(endpoint.response).toBeUndefined();
  });

  it("DocEndpoint optional fields accept expected types", () => {
    const endpoint: DocEndpoint = {
      method: "POST",
      path: "/create",
      description: "Create endpoint",
      auth: true,
      params: [{ name: "body", type: "string", required: true, desc: "Request body" }],
      response: '{"ok": true}',
    };
    expect(endpoint.auth).toBe(true);
    expect(Array.isArray(endpoint.params)).toBe(true);
    expect(typeof endpoint.response).toBe("string");
  });

  it("DocSection can be constructed with only mandatory fields", () => {
    const section: DocSection = {
      id: "test-section",
      title: "Test",
      description: "A test section",
      code: [{ language: "cURL", code: "curl /test" }],
    };
    expect(section.id).toBe("test-section");
    expect(section.endpoints).toBeUndefined();
    expect(section.details).toBeUndefined();
  });

  it("SidebarGroup has correct shape", () => {
    const group: SidebarGroup = {
      label: "Test Group",
      sectionIds: ["test-section"],
    };
    expect(group.label).toBe("Test Group");
    expect(group.sectionIds).toHaveLength(1);
  });
});
