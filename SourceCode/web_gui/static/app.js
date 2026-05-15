const FILE_PATH_REGEX = /([A-Za-z]:(?:\\|\/)[^\r\n"'<>|?*]+?\.[A-Za-z0-9]{1,12}|\/(?:[\w.\-]+\/){2,}[\w.\-]+\.[A-Za-z0-9]{1,12})/g;

const COMPOSER_PLACEHOLDERS = {
  talk: [
    "Talk with Oathweaver...",
    "What's on your mind?",
    "Ask anything...",
    "Start a conversation...",
    "What are you thinking about?",
  ],
  forage: [
    "Discovery request...",
    "What should I research?",
    "Search and synthesize...",
    "Dig into a topic...",
  ],
  make: [
    "Make request...",
    "What should I build?",
    "Describe what you need...",
    "Create something...",
  ],
  plan: [
    "Planning request...",
    "What should I plan?",
    "Outline the implementation...",
    "Design the rollout...",
  ],
};
const HTTP_URL_REGEX = /https?:\/\/[^\s<>"'`]+/gi;
const MARKDOWN_LINK_URL_REGEX = /\[[^\]]*]\((https?:\/\/[^\s)]+)\)/gi;
const SOURCE_SECTION_HEADING_REGEX = /^\s{0,3}(?:#{1,6}\s*)?(?:sources?|references?|citations?)\s*:?\s*$/i;
const SOURCE_LINE_REGEX = /^\s*(?:[-*]|\d+[.)])\s+.+$/;
const ASSISTANT_HTML_CACHE = new WeakMap();
const ASSISTANT_SOURCE_STACK_CACHE = new WeakMap();
const FONT_CONFIG_API_URL = "/api/settings/fonts";
const FONT_CONFIG_URL = "/static/fonts/font-config.json";

const REFLECTION_HINT_REGEX = /self-reflection check\s*\(([a-z0-9]{6,})\)/gi;
const REFLECT_COMMAND_REGEX = /\/reflect-answer\s+([a-z0-9]{6,})\b/gi;
const PENDING_CREATED_REGEX = /pending action created:\s*(web_[a-z0-9]+)\b/gi;
const PENDING_COMMAND_REGEX = /\/action-(?:answer|ignore)\s+(web_[a-z0-9]+)\b/gi;
const FORAGE_HINT_REGEX = /\[FORAGE:\s*"([^"]+)"\]/gi;
const ADD_TASK_REGEX     = /\[ADD_TASK:\s*"([^"]+)"(?:[^\]]*due="([^"]*)")?\]/gi;
const ADD_EVENT_REGEX    = /\[ADD_EVENT:\s*"([^"]+)"(?:[^\]]*date="([^"]*)")?(?:[^\]]*time="([^"]*)")?\]/gi;
const ADD_SHOPPING_REGEX = /\[ADD_SHOPPING:\s*"([^"]+)"\]/gi;
const ADD_ROUTINE_REGEX  = /\[ADD_ROUTINE:\s*"([^"]+)"(?:[^\]]*schedule="([^"]*)")?(?:[^\]]*weekday="([^"]*)")?(?:[^\]]*day="([^"]*)")?(?:[^\]]*time="([^"]*)")?(?:[^\]]*until="([^"]*)")?\]/gi;
const PLANNER_PERSON_RELATION_OPTIONS = [
  { value: "son", label: "Son" },
  { value: "daughter", label: "Daughter" },
  { value: "wife", label: "Wife" },
  { value: "husband", label: "Husband" },
  { value: "nephew", label: "Nephew" },
  { value: "niece", label: "Niece" },
  { value: "uncle", label: "Uncle" },
  { value: "aunt", label: "Aunt" },
  { value: "sister", label: "Sister" },
  { value: "brother", label: "Brother" },
  { value: "friend", label: "Friend" },
];
const PLANNER_MEMBER_ROLE_OPTIONS = [
  { value: "owner", label: "Owner" },
  { value: "adult", label: "Adult" },
  { value: "child", label: "Child" },
];
const PLANNER_CONTACT_DETAIL_KEYS = [
  "nickname",
  "birthday",
  "age",
  "age_is_estimate",
  "gender",
  "school_or_work",
  "likes",
  "dislikes",
  "important_dates",
  "medical_notes",
  "email",
  "phone",
  "notes",
];
const PROJECT_PIPELINE_MODES = [
  { value: "discovery", label: "Discovery" },
  { value: "make", label: "Make" },
];
const TOPIC_TYPES = [
  { value: "computer_science_programming", label: "Computer Science / Programming" },
  { value: "mathematics",                  label: "Mathematics" },
  { value: "science",                      label: "Science" },
  { value: "history",                      label: "History" },
  { value: "writing_rhetoric",             label: "Writing / Rhetoric" },
  { value: "business_strategy",            label: "Business / Strategy" },
  { value: "law_policy",                   label: "Law / Policy" },
  { value: "engineering",                  label: "Engineering" },
  { value: "creative",                     label: "Creative" },
  { value: "general_research",             label: "General Research" },
];
const LIFE_ADMIN_PROFILE_DETAIL_FIELDS = [
  ["full_name", "Full name"],
  ["age", "Age"],
  ["gender", "Gender"],
  ["birthday", "Birthday"],
  ["location", "Location"],
  ["ancestry", "Ancestry"],
  ["health", "Health"],
  ["work", "Work"],
  ["likes", "Likes"],
  ["dislikes", "Dislikes"],
  ["notes", "Notes"],
];
const LIFE_ADMIN_FAMILY_DETAIL_FIELDS = [
  ["nickname", "Nickname"],
  ["age", "Age"],
  ["birthday", "Birthday"],
  ["gender", "Gender"],
  ["school_or_work", "School / Work"],
  ["likes", "Likes"],
  ["dislikes", "Dislikes"],
  ["important_dates", "Important dates"],
  ["medical_notes", "Medical notes"],
];
const LIFE_ADMIN_PET_DETAIL_FIELDS = [
  ["breed", "Breed"],
  ["sex", "Sex"],
  ["age", "Age"],
  ["birthday", "Birthday"],
  ["weight", "Weight"],
  ["food", "Food"],
  ["medications", "Medications"],
  ["vet", "Vet"],
  ["microchip", "Microchip"],
  ["behavior_notes", "Behavior"],
];
const MAKE_TARGETS = [
  { value: "auto",         label: "Auto" },
  { value: "essay",        label: "Essay" },
  { value: "brief",        label: "Brief" },
  { value: "app",          label: "App" },
  { value: "product",      label: "Product" },
  { value: "gap_analysis", label: "Gap Analysis" },
  { value: "novel",        label: "Novel" },
  { value: "report",       label: "Report" },
  { value: "tool",         label: "Tool / Script" },
];
const PLANNER_MONTH_VIEW_PAST_OFFSET = -2;
const PLANNER_MONTH_VIEW_FUTURE_OFFSET = 12;
const AGENT_GRAPH_VIEW_WIDTH = 1400;
const AGENT_GRAPH_VIEW_HEIGHT = 840;
const AGENT_GRAPH_MIN_ZOOM = 0.45;
const AGENT_GRAPH_MAX_ZOOM = 2.4;
const HOME_COMPANION_DEFAULT_NAME = "Scout";
const HOME_PHRASE_WINDOWS = [
  { key: "night", startHour: 0, endHour: 4 },
  { key: "morning", startHour: 5, endHour: 11 },
  { key: "afternoon", startHour: 12, endHour: 16 },
  { key: "evening", startHour: 17, endHour: 21 },
  { key: "night", startHour: 22, endHour: 23 },
];
const WEATHER_CODE_LABELS = {
  0: "Clear",
  1: "Mostly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Freezing fog",
  51: "Light drizzle",
  53: "Drizzle",
  55: "Dense drizzle",
  56: "Light freezing drizzle",
  57: "Freezing drizzle",
  61: "Light rain",
  63: "Rain",
  65: "Heavy rain",
  66: "Light freezing rain",
  67: "Freezing rain",
  71: "Light snow",
  73: "Snow",
  75: "Heavy snow",
  77: "Snow grains",
  80: "Light showers",
  81: "Showers",
  82: "Heavy showers",
  85: "Light snow showers",
  86: "Heavy snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm with hail",
  99: "Severe thunderstorm with hail",
};
const HOME_COMPANION_SKETCHES = [
  {
    id: "sit",
    lines: [
      "M32 206 C58 192 90 190 120 196 C152 202 182 201 210 190",
      "M74 161 C66 126 78 98 104 88 C133 76 165 88 176 118 C184 140 184 163 171 177 C155 193 131 198 108 193 C90 189 78 178 74 161",
      "M96 84 C85 70 86 50 99 37 C114 23 136 23 151 36 C167 49 169 72 157 87",
      "M97 49 L82 31",
      "M153 47 L172 33",
      "M112 72 C120 79 130 79 138 72",
      "M116 93 C122 99 130 99 136 93",
      "M83 147 C73 156 68 173 74 189",
      "M163 152 C176 164 179 181 169 196",
      "M103 186 C96 198 95 210 102 220",
      "M145 187 C152 199 153 212 148 222",
      "M122 108 C124 111 127 111 130 108",
      "M111 117 C115 121 120 123 126 123 C132 123 137 121 141 117",
    ],
  },
  {
    id: "alert",
    lines: [
      "M28 206 C56 194 96 193 126 198 C157 203 186 203 214 192",
      "M68 164 C60 134 67 109 87 96 C106 83 132 84 149 95 C168 108 179 130 176 155 C173 182 151 200 123 201 C95 202 75 189 68 164",
      "M72 93 C60 82 57 64 64 50 C72 35 88 28 104 32 C117 35 128 44 132 56",
      "M131 59 C139 44 151 34 168 33 C183 33 197 42 202 57 C206 70 203 83 193 94",
      "M80 111 C95 103 108 103 121 112",
      "M119 97 C124 102 130 104 137 104 C144 104 150 102 156 97",
      "M91 150 C78 158 71 173 74 188",
      "M160 154 C173 164 179 180 171 195",
      "M106 189 C102 202 104 215 112 224",
      "M143 190 C147 203 146 215 140 224",
      "M109 121 C112 124 115 124 118 121",
      "M95 129 C102 136 111 139 121 139 C131 139 140 136 147 129",
    ],
  },
  {
    id: "rest",
    lines: [
      "M36 205 C63 196 90 194 118 198 C148 202 180 201 208 191",
      "M72 168 C67 146 73 123 89 109 C106 94 129 90 149 99 C171 108 183 129 181 151 C179 173 163 191 141 197 C116 204 87 197 72 168",
      "M90 106 C80 96 76 81 80 67 C84 52 97 40 112 37 C127 35 141 42 149 54",
      "M149 58 C156 45 169 37 184 38 C198 39 210 49 214 63 C218 77 213 91 202 100",
      "M98 120 C108 125 120 126 131 122",
      "M118 112 C121 115 124 115 127 112",
      "M95 151 C109 163 128 165 143 156",
      "M84 176 C77 188 77 203 86 214",
      "M152 176 C161 188 163 204 156 217",
      "M167 130 C176 126 185 129 192 136",
      "M170 118 C178 114 186 115 193 121",
    ],
  },
];

function escapeHtml(unsafe) {
  const div = document.createElement("div");
  div.textContent = String(unsafe || "");
  return div.innerHTML;
}

function normalizeProjectSlug(raw) {
  const text = String(raw || "").trim();
  const cleaned = text.replace(/\s+/g, "_").toLowerCase();
  return cleaned || "general";
}

function normalizeTopicId(raw) {
  return String(raw || "").trim() || "general";
}

function urlBase64ToUint8Array(base64String) {
  const padded = `${String(base64String || "").trim()}${"=".repeat((4 - (String(base64String || "").trim().length % 4 || 4)) % 4)}`
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(padded);
  const output = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return output;
}

function isInstalledWebApp() {
  try {
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
      return true;
    }
  } catch (_err) {}
  return Boolean(window.navigator && window.navigator.standalone);
}

function isProbablyIosDevice() {
  const ua = String(window.navigator?.userAgent || "");
  const platform = String(window.navigator?.platform || "");
  const maxTouchPoints = Number(window.navigator?.maxTouchPoints || 0);
  return /iPad|iPhone|iPod/i.test(ua) || (platform === "MacIntel" && maxTouchPoints > 1);
}

function supportsWebPushClient() {
  return Boolean(
    window.isSecureContext &&
      "Notification" in window &&
      "serviceWorker" in navigator &&
      "PushManager" in window
  );
}

function cloneLifeAdminRecord(source, defaults) {
  const base = typeof defaults === "function" ? defaults() : { ...(defaults || {}) };
  for (const key of Object.keys(base)) {
    base[key] = String(source && source[key] != null ? source[key] : "").trim();
  }
  return base;
}

function blankLifeAdminProfileForm() {
  return {
    preferred_name: "",
    full_name: "",
    age: "",
    gender: "",
    birthday: "",
    location: "",
    ancestry: "",
    health: "",
    work: "",
    likes: "",
    dislikes: "",
    notes: "",
  };
}

function blankLifeAdminFamilyForm() {
  return {
    name: "",
    relationship: "",
    notes: "",
    nickname: "",
    age: "",
    birthday: "",
    gender: "",
    school_or_work: "",
    likes: "",
    dislikes: "",
    important_dates: "",
    medical_notes: "",
  };
}

function blankLifeAdminPetForm() {
  return {
    name: "",
    species: "",
    notes: "",
    breed: "",
    sex: "",
    age: "",
    birthday: "",
    weight: "",
    food: "",
    medications: "",
    vet: "",
    microchip: "",
    behavior_notes: "",
  };
}

function blankWaypointContactDetails() {
  return {
    nickname: "",
    birthday: "",
    age: "",
    age_is_estimate: false,
    gender: "",
    school_or_work: "",
    likes: "",
    dislikes: "",
    important_dates: "",
    medical_notes: "",
    email: "",
    phone: "",
    notes: "",
  };
}

function blankWaypointContactFormDefaults() {
  return {
    name: "",
    kind: "person",
    relationship: "friend",
    location_name: "",
    location_address: "",
    ...blankWaypointContactDetails(),
  };
}

function blankWaypointMemberFormDefaults() {
  return {
    name: "",
    kind: "person",
    relationship: "wife",
    member_role: "adult",
    create_login: false,
    username: "",
    pin: "",
    color: "#4285f4",
    location_name: "",
    location_address: "",
    ...blankWaypointContactDetails(),
  };
}

function blankWaypointMemberEditorForm(color = "#4285f4") {
  return {
    id: "",
    name: "",
    kind: "person",
    relationship: "wife",
    member_role: "adult",
    create_login: false,
    profile_user_id: "",
    username: "",
    pin: "",
    color,
    location_name: "",
    location_address: "",
    ...blankWaypointContactDetails(),
  };
}

function homePhraseWindowKey(rawDate) {
  const d = rawDate instanceof Date ? rawDate : new Date(rawDate);
  const hour = d.getHours();
  for (const row of HOME_PHRASE_WINDOWS) {
    if (hour >= row.startHour && hour <= row.endHour) {
      return row.key;
    }
  }
  return "day";
}

function normalizeInlineFilePath(rawPath) {
  const text = String(rawPath || "").trim();
  if (!text) {
    return "";
  }
  try {
    return decodeURIComponent(text);
  } catch (_err) {
    return text;
  }
}

function formatInlineMarkdown(line) {
  const raw = String(line || "");
  const fileLinkTokens = [];
  const withLinkPlaceholders = raw.replace(/\[([^\]]+)\]\(\/api\/files\/read\?path=([^)]+)\)/g, (_match, label, rawPath) => {
    const idx = fileLinkTokens.push({
      label: String(label || "").trim(),
      path: normalizeInlineFilePath(rawPath),
    }) - 1;
    return `@@GB_FILE_LINK_${idx}@@`;
  });
  const fileTokens = [];
  FILE_PATH_REGEX.lastIndex = 0;
  const tokenized = withLinkPlaceholders.replace(FILE_PATH_REGEX, (matchedPath) => {
    const idx = fileTokens.push(matchedPath) - 1;
    return `@@GB_FILE_${idx}@@`;
  });

  let html = escapeHtml(tokenized);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/@@GB_FILE_LINK_(\d+)@@/g, (_match, idxText) => {
    const idx = Number(idxText || -1);
    const row = idx >= 0 && idx < fileLinkTokens.length ? fileLinkTokens[idx] : null;
    if (!row || !row.path) {
      return "";
    }
    const label = row.label || row.path;
    return `<button type="button" class="md-inline-link file-inline-link" data-file-path="${encodeURIComponent(row.path)}">${escapeHtml(label)}</button>`;
  });
  html = html.replace(/@@GB_FILE_(\d+)@@/g, (_match, idxText) => {
    const idx = Number(idxText || -1);
    const matchedPath = idx >= 0 && idx < fileTokens.length ? fileTokens[idx] : "";
    if (!matchedPath) {
      return "";
    }
    return `<button type="button" class="md-inline-link file-inline-link" data-file-path="${encodeURIComponent(matchedPath)}">${escapeHtml(
      matchedPath
    )}</button>`;
  });
  return html;
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let listMode = "";
  let inCode = false;
  const codeLines = [];

  const closeList = () => {
    if (listMode === "ul") {
      html.push("</ul>");
    } else if (listMode === "ol") {
      html.push("</ol>");
    }
    listMode = "";
  };

  const openList = (nextMode) => {
    const target = nextMode === "ol" ? "ol" : "ul";
    if (listMode === target) {
      return;
    }
    closeList();
    html.push(target === "ol" ? "<ol>" : "<ul>");
    listMode = target;
  };

  const flushCode = () => {
    if (codeLines.length === 0) {
      return;
    }
    closeList();
    const block = escapeHtml(codeLines.join("\n"));
    html.push(`<pre><code>${block}</code></pre>`);
    codeLines.length = 0;
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        inCode = false;
        flushCode();
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      html.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      openList("ul");
      html.push(`<li>${formatInlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (numbered) {
      openList("ol");
      html.push(`<li>${formatInlineMarkdown(numbered[1])}</li>`);
      continue;
    }

    const quote = line.match(/^\s*>\s?(.*)$/);
    if (quote) {
      closeList();
      html.push(`<blockquote>${formatInlineMarkdown(quote[1])}</blockquote>`);
      continue;
    }

    if (!line.trim()) {
      closeList();
      html.push('<div class="md-gap"></div>');
      continue;
    }

    closeList();
    html.push(`<p>${formatInlineMarkdown(line)}</p>`);
  }

  if (inCode) {
    flushCode();
  }
  closeList();
  return html.join("");
}

function normalizeDetectedUrl(rawUrl) {
  let text = String(rawUrl || "").trim();
  if (!text) {
    return "";
  }
  if (text.startsWith("<") && text.endsWith(">")) {
    text = text.slice(1, -1).trim();
  }
  while (text && /[.,;!?]+$/.test(text)) {
    text = text.slice(0, -1);
  }
  while (text.endsWith(")") && (text.match(/\(/g) || []).length < (text.match(/\)/g) || []).length) {
    text = text.slice(0, -1);
  }
  return text.trim();
}

function sourceDomainFromUrl(rawUrl) {
  const normalized = normalizeDetectedUrl(rawUrl);
  if (!normalized) {
    return "";
  }
  try {
    const parsed = new URL(normalized);
    const host = String(parsed.hostname || "").trim().toLowerCase();
    return host.replace(/^www\./, "");
  } catch (_err) {
    return "";
  }
}

function sourceIconUrlForDomain(domain) {
  const safeDomain = String(domain || "").trim().toLowerCase();
  if (!safeDomain) {
    return "";
  }
  return `https://www.google.com/s2/favicons?sz=64&domain=${encodeURIComponent(safeDomain)}`;
}

function collectSourceEntriesFromText(text) {
  const raw = String(text || "");
  const rows = [];
  const seenKeys = new Set();
  const pushSource = (rawUrl, rawDomain = "", rawTitle = "") => {
    let domain = String(rawDomain || "").trim().toLowerCase();
    domain = domain.replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "").replace(/:\d+$/, "");
    const url = normalizeDetectedUrl(rawUrl);
    if (!domain && url) {
      domain = sourceDomainFromUrl(url);
    }
    const key = String(url || domain || "").trim().toLowerCase();
    if (!key || (!domain && !url) || seenKeys.has(key)) {
      return;
    }
    seenKeys.add(key);
    rows.push({
      domain,
      url: url || (domain ? `https://${domain}` : ""),
      icon: sourceIconUrlForDomain(domain),
      letter: domain.slice(0, 1).toUpperCase() || "?",
      title: String(rawTitle || "").trim(),
    });
  };

  MARKDOWN_LINK_URL_REGEX.lastIndex = 0;
  let mdMatch;
  while ((mdMatch = MARKDOWN_LINK_URL_REGEX.exec(raw)) !== null) {
    pushSource(mdMatch[1]);
  }

  HTTP_URL_REGEX.lastIndex = 0;
  let urlMatch;
  while ((urlMatch = HTTP_URL_REGEX.exec(raw)) !== null) {
    pushSource(urlMatch[0]);
  }

  return rows;
}

function collectSourceEntries(contentText, metadataSources) {
  const rows = [];
  const seenKeys = new Set();
  const pushSource = (rawUrl, rawDomain = "", rawTitle = "") => {
    let domain = String(rawDomain || "").trim().toLowerCase();
    domain = domain.replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "").replace(/:\d+$/, "");
    const url = normalizeDetectedUrl(rawUrl);
    if (!domain && url) {
      domain = sourceDomainFromUrl(url);
    }
    const key = String(url || domain || "").trim().toLowerCase();
    if (!key || (!domain && !url) || seenKeys.has(key)) {
      return;
    }
    seenKeys.add(key);
    rows.push({
      domain,
      url: url || (domain ? `https://${domain}` : ""),
      icon: sourceIconUrlForDomain(domain),
      letter: domain.slice(0, 1).toUpperCase() || "?",
      title: String(rawTitle || "").trim(),
    });
  };

  const meta = Array.isArray(metadataSources) ? metadataSources : [];
  for (const row of meta) {
    if (!row || typeof row !== "object") {
      continue;
    }
    pushSource(
      row.url || row.source_url || row.link || "",
      row.domain || row.source_domain || row.host || row.site || "",
      row.title || ""
    );
  }

  const contentRows = collectSourceEntriesFromText(contentText);
  for (const row of contentRows) {
    pushSource(row?.url || "", row?.domain || "");
  }
  return rows;
}

function stripTrailingSourceSection(text) {
  const raw = String(text || "");
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  if (!lines.length) {
    return "";
  }

  let end = lines.length - 1;
  while (end >= 0 && !String(lines[end] || "").trim()) {
    end -= 1;
  }
  if (end < 0) {
    return "";
  }

  let headingIndex = -1;
  for (let i = end; i >= Math.max(0, end - 20); i -= 1) {
    if (SOURCE_SECTION_HEADING_REGEX.test(String(lines[i] || "").trim())) {
      headingIndex = i;
      break;
    }
  }
  if (headingIndex >= 0) {
    let sourceLike = true;
    for (let i = headingIndex + 1; i <= end; i += 1) {
      const row = String(lines[i] || "").trim();
      if (!row) {
        continue;
      }
      const hasUrl = /https?:\/\/\S+/i.test(row);
      const looksLikeSourceLine = hasUrl || SOURCE_LINE_REGEX.test(row) || /^source\s*[:\-]/i.test(row);
      if (!looksLikeSourceLine) {
        sourceLike = false;
        break;
      }
    }
    if (sourceLike) {
      return lines.slice(0, headingIndex).join("\n").replace(/\n{3,}/g, "\n\n").trim();
    }
  }

  return raw.trim();
}

function collapseMarkdownLinksToLabels(text) {
  return String(text || "").replace(/\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/gi, (_match, label, url) => {
    const cleanLabel = String(label || "").trim();
    const domain = sourceDomainFromUrl(url);
    if (!cleanLabel || /^https?:\/\//i.test(cleanLabel)) {
      return domain || cleanLabel || "source";
    }
    return cleanLabel;
  });
}

function collapsePlainUrlsToDomains(text) {
  return String(text || "").replace(/https?:\/\/[^\s<>"'`]+/gi, (url) => {
    const domain = sourceDomainFromUrl(url);
    return domain || "source";
  });
}

function stripTrailingAssistantRule(text) {
  return String(text || "").replace(/(?:\n\s*\*\*\*\s*)+$/g, "").trimEnd();
}

function normalizeTalkDisplayMarkdown(text) {
  const trimmed = stripTrailingSourceSection(stripTrailingAssistantRule(String(text || "")));
  const noMarkdownLinks = collapseMarkdownLinksToLabels(trimmed);
  return collapsePlainUrlsToDomains(noMarkdownLinks).trim();
}

function researchReplyPayload(msg) {
  const meta = msg && typeof msg === "object" && msg.meta && typeof msg.meta === "object" ? msg.meta : {};
  const payload = meta && typeof meta.research_reply === "object" ? meta.research_reply : null;
  if (!payload) return null;
  const sentences = Array.isArray(payload.sentences) ? payload.sentences.filter((row) => row && typeof row === "object") : [];
  const chunks = Array.isArray(payload.retrieved_chunks) ? payload.retrieved_chunks.filter((row) => row && typeof row === "object") : [];
  if (!sentences.length) {
    return null;
  }
  return {
    text: String(payload.text || ""),
    sentences,
    chunks,
  };
}

function renderResearchMessageHtml(msg) {
  const payload = researchReplyPayload(msg);
  if (!payload) {
    return "";
  }
  const chunksById = {};
  const chunkOrder = [];
  for (const row of payload.chunks) {
    const id = String(row.id || "").trim();
    if (!id || chunksById[id]) continue;
    chunksById[id] = row;
    chunkOrder.push(id);
  }
  const refNumberById = {};
  for (let i = 0; i < chunkOrder.length; i += 1) {
    refNumberById[chunkOrder[i]] = i + 1;
  }

  const parts = [];
  for (const row of payload.sentences) {
    const text = String(row.text || "").trim();
    if (!text) continue;
    const citationIds = Array.isArray(row.citation_ids) ? row.citation_ids.map((x) => String(x || "").trim()).filter(Boolean) : [];
    let sentenceHtml = `<span class="citation-sentence">${escapeHtml(text)}`;
    for (const cid of citationIds) {
      const chunk = chunksById[cid];
      if (!chunk) continue;
      const num = refNumberById[cid] || 0;
      const domain = String(chunk.domain || sourceDomainFromUrl(String(chunk.url || "")) || "source").trim();
      const url = String(chunk.url || "").trim();
      const snippet = String(chunk.snippet || "").trim().slice(0, 300);
      const score = Number(chunk.score || 0);
      const weakClass = score > 0 && score < 0.6 ? " is-weak" : "";
      const label = `Citation ${num || "?"}, source ${domain}, confidence ${score.toFixed(2)}`;
      const tip = `${domain}${snippet ? ` — ${snippet}` : ""}`;
      sentenceHtml +=
        `<sup class="citation-ref${weakClass}">` +
        `<a class="citation-link" href="${escapeHtml(url || "#")}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(label)}" title="${escapeHtml(tip)}">[${num || "?"}]</a>` +
        `<span class="citation-popover" role="tooltip"><strong>${escapeHtml(domain)}</strong><br>${escapeHtml(snippet || "Source snippet unavailable.")}</span>` +
        `</sup>`;
    }
    sentenceHtml += `</span>`;
    parts.push(sentenceHtml);
  }

  if (!parts.length) return "";
  return `<div class="research-citations">${parts.join(" ")}</div>`;
}

function startsWithEmoji(text) {
  return /^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(String(text || "").trim());
}

function decorateAssistantMarkdown(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  return lines
    .map((line) => {
      const heading = String(line || "").match(/^(#{1,6}\s+)(.*)$/);
      if (heading) {
        const level = Math.max(1, Math.min(6, String(heading[1] || "").trim().length));
        const body = String(heading[2] || "").trim();
        if (!body || startsWithEmoji(body)) {
          return line;
        }
        if (level === 1) return `${heading[1]}\u2728 ${body}`;
        if (level === 2) return `${heading[1]}\uD83D\uDD39 ${body}`;
        if (level === 3) return `${heading[1]}\uD83D\uDCDD ${body}`;
        return line;
      }

      const boldHeading = String(line || "").match(/^\s*\*\*([^*][^*]{1,80})\*\*\s*:?\s*$/);
      if (boldHeading) {
        const label = String(boldHeading[1] || "").trim();
        if (!label) {
          return line;
        }
        return `### ${startsWithEmoji(label) ? label : `\uD83D\uDCDD ${label}`}`;
      }
      return line;
    })
    .join("\n");
}

function stripTalkPrefix(text) {
  const raw = String(text || "");
  const low = raw.trim().toLowerCase();
  if (low === "/talk") {
    return "";
  }
  if (low.startsWith("/talk ")) {
    return raw.trim().slice(6);
  }
  return raw;
}

function extractAssistantActionTargets(text) {
  const raw = String(text || "");
  const reflections = new Set();
  const pending = new Set();
  let match;

  REFLECTION_HINT_REGEX.lastIndex = 0;
  while ((match = REFLECTION_HINT_REGEX.exec(raw)) !== null) {
    reflections.add(String(match[1] || "").trim().toLowerCase());
  }

  REFLECT_COMMAND_REGEX.lastIndex = 0;
  while ((match = REFLECT_COMMAND_REGEX.exec(raw)) !== null) {
    reflections.add(String(match[1] || "").trim().toLowerCase());
  }

  PENDING_CREATED_REGEX.lastIndex = 0;
  while ((match = PENDING_CREATED_REGEX.exec(raw)) !== null) {
    pending.add(String(match[1] || "").trim().toLowerCase());
  }

  PENDING_COMMAND_REGEX.lastIndex = 0;
  while ((match = PENDING_COMMAND_REGEX.exec(raw)) !== null) {
    pending.add(String(match[1] || "").trim().toLowerCase());
  }

  const forageSeeds = [];
  FORAGE_HINT_REGEX.lastIndex = 0;
  const _forageMatch = FORAGE_HINT_REGEX.exec(raw);
  if (_forageMatch) {
    const seed = String(_forageMatch[1] || "").trim();
    if (seed) forageSeeds.push(seed);
  }

  const waypointActions = [];
  ADD_TASK_REGEX.lastIndex = 0;
  while ((match = ADD_TASK_REGEX.exec(raw)) !== null) {
    const title = String(match[1] || "").trim();
    const due   = String(match[2] || "").trim();
    if (title) waypointActions.push({ type: "task", title, due });
  }
  ADD_EVENT_REGEX.lastIndex = 0;
  while ((match = ADD_EVENT_REGEX.exec(raw)) !== null) {
    const title = String(match[1] || "").trim();
    const date  = String(match[2] || "").trim();
    const time  = String(match[3] || "").trim();
    if (title) waypointActions.push({ type: "event", title, date, time });
  }
  ADD_SHOPPING_REGEX.lastIndex = 0;
  while ((match = ADD_SHOPPING_REGEX.exec(raw)) !== null) {
    const item = String(match[1] || "").trim();
    if (item) waypointActions.push({ type: "shopping", title: item });
  }

  ADD_ROUTINE_REGEX.lastIndex = 0;
  while ((match = ADD_ROUTINE_REGEX.exec(raw)) !== null) {
    const title    = String(match[1] || "").trim();
    const schedule = String(match[2] || "weekly_day").trim();
    const weekday  = String(match[3] || "").trim();
    const day      = String(match[4] || "").trim();
    const time     = String(match[5] || "").trim();
    const until    = String(match[6] || "").trim();
    if (title) waypointActions.push({ type: "routine", title, schedule, weekday, day, time, until });
  }

  return {
    reflectionIds: Array.from(reflections).filter(Boolean),
    pendingIds: Array.from(pending).filter(Boolean),
    forageSeeds,
    waypointActions,
  };
}

function isIsoDate(text) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(text || "").trim());
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function startOfLocalDay(rawDate) {
  const d = rawDate instanceof Date ? rawDate : new Date(rawDate);
  if (Number.isNaN(d.getTime())) {
    return new Date();
  }
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function startOfWeek(rawDate) {
  const d = startOfLocalDay(rawDate);
  d.setDate(d.getDate() - d.getDay());
  return d;
}

function addDays(rawDate, days) {
  const d = startOfLocalDay(rawDate);
  d.setDate(d.getDate() + days);
  return d;
}

function addMonths(rawDate, months) {
  const d = startOfLocalDay(rawDate);
  d.setDate(1);
  d.setMonth(d.getMonth() + months);
  return d;
}

function daysInMonth(year, monthIndex) {
  return new Date(year, monthIndex + 1, 0).getDate();
}

function addMonthsClamped(rawDate, months) {
  const d = startOfLocalDay(rawDate);
  const year = d.getFullYear();
  const monthIndex = d.getMonth();
  const day = d.getDate();
  const target = new Date(year, monthIndex + Number(months || 0), 1);
  const maxDay = daysInMonth(target.getFullYear(), target.getMonth());
  target.setDate(Math.min(day, maxDay));
  return startOfLocalDay(target);
}

function normalizeRecurrenceType(raw) {
  const value = String(raw || "none").trim().toLowerCase();
  if (["weekly_day", "monthly_day_of_month", "monthly_nth_weekday"].includes(value)) {
    return value;
  }
  return "none";
}

function jsDayToMonday0(jsDay) {
  const value = Number(jsDay || 0);
  return (value + 6) % 7;
}

function monday0ToJsDay(value) {
  const day = Number(value || 0);
  return (day + 1) % 7;
}

function nthWeekdayInMonth(year, monthIndex, weekday, nth) {
  const wd = Math.max(0, Math.min(6, Number(weekday || 0)));
  const n = Math.max(1, Math.min(5, Number(nth || 1)));
  if (n === 5) {
    const last = new Date(year, monthIndex + 1, 0);
    const back = (last.getDay() - wd + 7) % 7;
    return new Date(year, monthIndex, last.getDate() - back);
  }
  const first = new Date(year, monthIndex, 1);
  const offset = (wd - first.getDay() + 7) % 7;
  const day = 1 + offset + (n - 1) * 7;
  if (day > daysInMonth(year, monthIndex)) {
    return null;
  }
  return new Date(year, monthIndex, day);
}

function toDateKey(rawDate) {
  const d = startOfLocalDay(rawDate);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function parseDateKey(raw) {
  const text = String(raw || "").trim();
  if (!isIsoDate(text)) {
    return null;
  }
  const [y, m, d] = text.split("-").map((x) => Number(x));
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) {
    return null;
  }
  return new Date(y, m - 1, d);
}

function normalizeTimeText(raw) {
  const text = String(raw || "").trim();
  const match = text.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) {
    return "";
  }
  const hh = Number(match[1]);
  const mm = Number(match[2]);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) {
    return "";
  }
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
    return "";
  }
  return `${pad2(hh)}:${pad2(mm)}`;
}

function timeTextToMinutes(raw) {
  const normalized = normalizeTimeText(raw);
  if (!normalized) {
    return 24 * 60 + 1;
  }
  const parts = normalized.split(":").map((x) => Number(x));
  const hh = Number.isFinite(parts[0]) ? parts[0] : 0;
  const mm = Number.isFinite(parts[1]) ? parts[1] : 0;
  return hh * 60 + mm;
}

function blankAgentGraphData() {
  return {
    generated_at: "",
    summary: {
      active_jobs: 0,
      foraging_jobs: 0,
      building_jobs: 0,
      active_agents: 0,
      foraging_active_agents: 0,
      building_active_agents: 0,
    },
    nodes: [],
    edges: [],
  };
}

if (!window.Vue || !document.getElementById("app")) {
  throw new Error("Vue runtime or #app mount node is missing.");
}

const app = window.Vue.createApp({
  data() {
    return {
      conversations: [],
      sidebarProjectRows: [],
      sidebarTopicRows: [],
      sidebarProjectsLoading: false,
      sidebarProjectsFetchedAt: 0,
      sidebarProjectsError: "",
      activeConversationId: null,
      activeConversation: null,
      activeProject: "general",
      activeApp: "home",
      homePhrase: "",
      homeCurrentTime: "",
      homeWeatherExpanded: false,
      homeWeatherLocationDraft: "",
      homeWeather: {
        locationQuery: "",
        locationLabel: "",
        latitude: null,
        longitude: null,
        timezone: "auto",
        temperatureF: null,
        apparentF: null,
        highF: null,
        lowF: null,
        weatherCode: null,
        windMph: null,
        precipitationChance: null,
        isDay: null,
        updatedAt: "",
        loading: false,
        error: "",
      },
      homeCompanionSketches: HOME_COMPANION_SKETCHES,
      homeCompanionIndex: 0,
      homeCompanionName: HOME_COMPANION_DEFAULT_NAME,
      homeCompanionNameDraft: HOME_COMPANION_DEFAULT_NAME,
      homeCompanionRenaming: false,
      inputMode: "talk",
      theme: "Night",
      themeOptions: ["Night", "Day"],
      fontOptions: [],
      activeFontId: "",
      fontConfigError: "",
      topicTypeOptions: TOPIC_TYPES,
      draft: "",
      conversationDrafts: {},
      conversationComposerState: {},
      composerImages: [],
      composerAddMenuOpen: false,
      composerImageStyle: "realistic",
      composerLoraOptions: [],
      composerSelectedLoras: [],
      composerLoraLoading: false,
      composerLoraError: "",
      imageToolPresetOptions: [],
      imageToolPresetLoading: false,
      imageToolPresetError: "",
      imageToolStyleModalOpen: false,
      imageToolPromptModalOpen: false,
      imageToolSelectedStyle: {
        kind: "realistic",
        label: "Realistic (SD3.5)",
        modelFamily: "",
        familyTag: "",
        loras: [],
        stylePresetId: "",
        defaultSteps: 28,
        defaultRefinePrompt: true,
        defaultNegativePrompt: "",
        defaultWidth: 768,
        defaultHeight: 768,
      },
      imageToolAspect: "square",
      imageToolSubject: "",
      lightboxOpen: false,
      lightboxUrl: "",
      lightboxName: "",
      postbagItemOpen: false,
      postbagItemData: null,
      imageToolPrompt: "",
      imageToolNegativePrompt: "",
      imageToolRefinePrompt: true,
      imageToolSteps: 28,
      imageToolStepDefaults: {},
      imageToolStepDefaultsLoaded: false,
      imageToolDefaultSaveNote: "",
      imageToolUseComposerRefs: false,
      imageToolBusy: false,
      imageToolError: "",
      imageToolLastPromptFinal: "",
      imageToolSlashMenuOpen: false,
      imageToolSlashInsertStart: 0,
      bgEnhanceBusy: {},
      videoToolOpen: false,
      videoToolBusy: false,
      videoToolError: "",
      videoToolPrompt: "",
      videoToolNegativePrompt: "",
      videoToolRefImage: null,
      videoToolNumFrames: 81,
      replyTargetMsg: null,
      voiceSupported: false,
      voiceActive: false,
      ttsEnabled: false,
      _voiceRecognition: null,
      sendingByConversation: {},
      queuedByConversation: {},
      sendingJobStage: {},
      pendingJobEvents: {},
      pendingJobAgentTracker: {},
      completedThinkStreams: {},
      expandedThinkTrees: {},
      assistantTypingByMessage: {},
      quickActionBusy: {},
      completedQuickActions: {},
      completedWaypointActions: {},
      chatMenuOpen: false,
      sidebarOpen: false,
      sidebarCollapsed: false,
      mdOverlayOpen: false,
      actionsOverlayOpen: false,
      panelOverlayOpen: false,
      agentGraphModalOpen: false,
      agentGraphLoading: false,
      agentGraphError: "",
      agentGraphData: blankAgentGraphData(),
      agentGraphPositions: {},
      agentGraphSelectedNodeId: "",
      agentGraphZoom: 1,
      agentGraphPan: { x: 28, y: 20 },
      agentGraphDragState: null,
      agentGraphPanState: null,
      agentGraphActivePointers: {},
      agentGraphPinchState: null,
      mdTitle: "File Preview",
      mdPath: "",
      mdHtml: "",
      panelStatus: {
        pending_actions: 0,
        open_reflections: 0,
        learned_lessons: 0,
        handoff_waiting_output: 0,
        handoff_ready_for_ingest: 0,
        pending_handoffs: 0,
        active_projects: 0,
        web_mode: "auto",
        cloud_mode: "off",
        foraging_paused: false,
        foraging_active_jobs: 0,
        foraging_yielding: false,
        foraging_completion_unread: false,
        building_paused: false,
        building_active_jobs: 0,
        building_completion_unread: false,
        cards_unread: 0,
        action_proposals_pending: 0,
        watchtower_active: 0,
        topics_with_research: 0,
        library_items_total: 0,
        library_items_pending: 0,
      },
      makeType: localStorage.getItem("oathweaver_make_type") || "",
      makeTypeModalOpen: false,
      makeOutputEditModalOpen: false,
      makeOutputEditLoading: false,
      makeOutputEditRows: [],
      pendingExtendsRequestId: "",
      pendingExtendsTitle: "",
      makeTypeCatalog: [],
      watchtowerForm: { topic: "", profile: "general", schedule: "daily", schedule_hour: 7 },
      actionProposals: [],
      jobWebStack: {},
      pendingLiveSources: {},
      sourceExpandedMsgs: {},
      lessonsUnreadCount: 0,
      growthActiveTab: "postbag",
      growthPostbagRows: [],
      growthReflectionsRows: [],
      growthLessonsRows: [],
      lessonsReadIds: {},
      lessonsUnreadCheckedAt: 0,
      reflectionsUnreadCount: 0,
      reflectionsReadIds: {},
      reflectionsUnreadCheckedAt: 0,
      pendingActions: [],
      pendingActionsLoading: false,
      panelKey: "",
      panelData: [],
      libraryIntakeOpen: false,
      libraryIntakeSubmitting: false,
      libraryIntakeFiles: [],
      libraryIntakeTitle: "",
      libraryIntakeSourceKind: "general",
      libraryIntakeDomain: "",
      libraryIntakeTopicId: "",
      libraryIntakeProjectSlug: "",
      libraryIntakeError: "",
      libraryFilter: {
        search: "",
        status: "all",
        kind: "all",
        topic_id: "",
        project_slug: "",
      },
      libraryDetailItem: null,
      contentTreeRoot: "",
      contentTreeNodes: [],
      contentTreeNodeCount: 0,
      contentTreeTruncated: false,
      contentTreeExpanded: {},
      _contentTreeProject: "",
      lessonsSortBy: "newest",
      lessonsViewMode: "current",
      panelLoading: false,
      projectDetail: null,
      projectPipeline: {
        project: "general",
        mode: "discovery",
        target: "auto",
        topic_type: "general",
        updated_at: "",
      },
      topicForm: { name: "", type: "", description: "", seed_question: "", parent_id: "" },
      topicPickerOpen: false,
      topicPickerSearch: "",
      topicPickerRows: [],
      topicPickerMode: "set",
      undergroundWarningOpen: false,
      undergroundWarningPendingTopic: null,
      topicFormUndergroundWarning: false,
      activeTopicId: "general",
      topicDetailData: null,
      _activePanelTopicId: "",
      lessonsFilterByTopic: false,
      sidebarPanelsCollapsed: true,
      resetModalOpen: false,
      resetConfirmText: "",
      resetRunning: false,
      resetLog: [],
      waypoint: {
        thread_id: "waypoint_main",
        messages: [],
        tasks: [],
        reminders: [],
        events: [],
        event_patterns: [],
        insights: { summary_lines: [], priorities: [], watchouts: [], suggestions: [], patterns: [], conflicts: [], counts: {}, week_window: {} },
        shopping_food: [],
        shopping_general: [],
        contacts: [],
        members: [],
        contact_locations: [],
        open_tasks_count: 0,
        open_reminders_count: 0,
        profile_color: "#4285f4",
      },
      waypointLoaded: false,
      waypointTopTab: "calendar",
      waypointDraft: "",
      waypointBuilderOpen: false,
      waypointBuilder: {
        command: "shopping_add",
        shopping_category: "food",
        shopping_item: "",
        shopping_items: "",
        shopping_id: "",
        task_title: "",
        task_due_date: "",
        task_priority: "medium",
        task_id: "",
        task_reason: "",
        event_title: "",
        event_date: "",
        event_start: "",
        event_end: "",
        event_location_contact_id: "",
        event_location: "",
        event_id: "",
      },
      waypointSending: false,
      waypointInsightBusy: {},
      waypointChatExpanded: false,
      waypointTaskSubmitting: false,
      waypointEventSubmitting: false,
      waypointShoppingSubmitting: false,
      waypointContactSubmitting: false,
      waypointMemberSubmitting: false,
      waypointMemberEditorOpen: false,
      waypointMemberEditorSubmitting: false,
      waypointMemberEditorMode: "add",
      waypointMemberDeleteConfirm: "",
      waypointMemberEditorDetailsOpen: false,
      waypointTaskModalOpen: false,
      waypointTaskEditId: "",
      waypointEventModalOpen: false,
      waypointEventEditId: "",
      waypointShoppingModalOpen: false,
      waypointShoppingEditId: "",
      waypointContactModalOpen: false,
      waypointContactEditId: "",
      waypointContactDeleteConfirm: "",
      waypointContactDetailsOpen: false,
      projectPickerOpen: false,
      projectPickerLoading: false,
      projectPickerSubmitting: false,
      projectPickerSearch: "",
      projectPickerRows: [],
      projectPickerForm: {
        project: "",
        description: "",
      },
      projectPickerError: "",
      projectBranchModalOpen: false,
      projectBranchSubmitting: false,
      projectBranchSearch: "",
      projectBranchError: "",
      projectBranchForm: {
        project: "",
        description: "",
        mode: "clone",
        copy_project_data: false,
      },
      projectTargetModalOpen: false,
      projectTargetSubmitting: false,
      projectTargetError: "",
      projectTargetForm: {
        target: "auto",
      },
      projectTopicTypeModalOpen: false,
      projectTopicTypeSubmitting: false,
      projectTopicTypeError: "",
      projectTopicTypeForm: {
        topic_type: "general",
      },
      waypointMemberEditorForm: blankWaypointMemberEditorForm("#4285f4"),
      familyProfileModalOpen: false,
      emailSettingsModalOpen: false,
      webPushModalOpen: false,
      morningDigestModalOpen: false,
      botSettingsModalOpen: false,
      botSettingsSubmitting: false,
      botConfig: {
        telegram: { enabled: false, bot_token: "" },
        discord: { enabled: false, bot_token: "" },
      },
      botMappings: [],
      botPending: [],
      botUserForm: { platform: "telegram", platform_user_id: "", platform_username: "", oathweaver_user_id: "" },
      botProfiles: [],
      digestSettings: { enabled: false, hour: 7, locationLabel: "", locationLat: null, locationLon: null },
      digestLocationDraft: "",
      emailSettingsSubmitting: false,
      emailSettingsForm: { notification_email: "", smtp_user: "", smtp_password: "", dnd_enabled: false, dnd_start: "22:00", dnd_end: "08:00" },
      webPushSubmitting: false,
      webPushSettings: {
        server_supported: false,
        public_key: "",
        vapid_subject: "",
        enabled: true,
        subscription_count: 0,
        has_subscription: false,
        last_error: "",
        last_test_sent_at: "",
      },
      webPushPermission: "default",
      webPushInstalled: false,
      webPushRegistrationReady: false,
      _webPushRegistration: null,
      familyProfileSubmitting: false,
      familyProfileForm: {
        username: "",
        display_name: "",
        role: "adult",
        color: "#4285f4",
        pin: "",
        pin_confirm: "",
      },
      waypointDayPanelExpanded: true,
      waypointTaskForm: {
        title: "",
        list_name: "general",
        priority: "medium",
        due_date: "",
        member_ids: [],
        location: "",
        recurrence_enabled: false,
        recurrence_type: "weekly_day",
        recurrence_interval: 1,
        recurrence_weekday: 0,
        recurrence_day: 1,
        recurrence_nth: 1,
        recurrence_until: "",
      },
      purchaseRecos: [],
      waypointEventForm: {
        title: "",
        date: "",
        start_time: "",
        end_time: "",
        reminder_time: "",
        location_contact_id: "",
        location: "",
        member_ids: [],
        recurrence_enabled: false,
        recurrence_type: "weekly_day",
        recurrence_interval: 1,
        recurrence_weekday: jsDayToMonday0(new Date().getDay()),
        recurrence_day: new Date().getDate(),
        recurrence_nth: 1,
        recurrence_until: "",
      },
      waypointShoppingForm: {
        title: "",
        category: "food",
      },
      waypointContactForm: blankWaypointContactFormDefaults(),
      waypointMemberForm: blankWaypointMemberFormDefaults(),
      waypointCalendarView: "month",
      waypointCalendarDate: startOfLocalDay(new Date()),
      waypointSelectedDateKey: toDateKey(startOfLocalDay(new Date())),
      waypointCalendarLabel: "Calendar",
      waypointCalendarHtml: "",
      waypointCalendarMemberFilterOpen: false,
      waypointMemberFilterPopStyle: {},
      waypointCalendarFilteredMemberIds: [],
      waypointCalendarTypeFilter: "both",
      waypointMonthPreviewOpen: false,
      auth: {
        enabled: false,
        authenticated: false,
        profile: null,
      },
      authSetup: {
        required: false,
        allowed: true,
        message: "",
        username: "owner",
        password: "",
        confirmPassword: "",
        submitting: false,
      },
      authShowForm: false,
      loginUsername: "",
      loginPassword: "",
      authError: "",
      thinkingNowTs: Date.now(),
      msgCopiedId: "",
      _boundWindowClick: null,
      _boundResize: null,
      _boundHashChange: null,
      _boundKeydown: null,
      _boundAgentGraphMouseMove: null,
      _boundAgentGraphMouseUp: null,
      _boundSwipeMove: null,
      _boundSidebarTouchStart: null,
      _boundSidebarTouchEnd: null,
      swipeOpen: {},
      _sidebarSwipeState: null,
      _waypointPollTimer: null,
      _panelPollTimer: null,
      _homePhraseTimer: null,
      _homeClockTimer: null,
      _blobStopFns: [],
      _homeWeatherPollTimer: null,
      _thinkingTimer: null,
      _composerPlaceholderTimer: null,
      _imageToolDefaultSaveTimer: null,
      composerPlaceholderIdx: 0,
      composerPlaceholderFading: false,
      _stableAppVh: 0,
      cancelEnableDelayMs: 1800000,
    };
  },

  computed: {
    digestHourOptions() {
      const fmt = (h) => {
        const ampm = h < 12 ? "AM" : "PM";
        const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
        return { value: h, label: `${h12}:00 ${ampm}` };
      };
      return [5, 6, 7, 8, 9, 10].map(fmt);
    },
    composerPlaceholder() {
      const mode = this.inputMode || "talk";
      const pool = COMPOSER_PLACEHOLDERS[mode] || COMPOSER_PLACEHOLDERS.talk;
      return pool[this.composerPlaceholderIdx % pool.length];
    },
    imageToolStyleButtons() {
      const rows = [{
        id: "realistic",
        kind: "realistic",
        label: "Realistic (SD3.5)",
        modelFamily: "",
        familyTag: "",
        loras: [],
        stylePresetId: "",
        defaultSteps: 28,
        defaultRefinePrompt: true,
        defaultNegativePrompt: "",
        defaultWidth: 768,
        defaultHeight: 768,
        disabled: false,
        installHint: "",
      }];
      for (const preset of (Array.isArray(this.imageToolPresetOptions) ? this.imageToolPresetOptions : [])) {
        const presetId = String(preset?.id || "").trim();
        if (!presetId) {
          continue;
        }
        const defaults = preset?.defaults && typeof preset.defaults === "object" ? preset.defaults : {};
        const resolved = String(preset?.resolved_lora_name || "").trim();
        const kind = String(preset?.kind || "lora").trim().toLowerCase() || "lora";
        const modelFamilyRaw = String(preset?.model_family || defaults?.model_family || "").trim().toLowerCase();
        const modelFamily = modelFamilyRaw === "sdxl" ? "xl" : modelFamilyRaw;
        const available = kind === "lora"
          ? (Boolean(preset?.available) && Boolean(resolved))
          : Boolean(preset?.available);
        rows.push({
          id: `preset:${presetId}`,
          kind: kind === "realistic" ? "realistic" : "lora",
          label: String(preset?.label || presetId).trim() || presetId,
          modelFamily,
          familyTag: modelFamily === "xl" ? "XL" : "",
          loras: available ? [resolved] : [],
          stylePresetId: presetId,
          defaultSteps: Number(defaults?.steps || 30),
          defaultRefinePrompt: defaults?.refine_prompt !== false,
          defaultNegativePrompt: String(preset?.default_negative_prompt || "").trim(),
          defaultWidth: Number(defaults?.width || 512),
          defaultHeight: Number(defaults?.height || 512),
          disabled: !available,
          installHint: String(preset?.install_hint || "").trim(),
        });
      }
      return rows;
    },
    imageToolResolutionLabel() {
      const dims = this.imageToolResolutionForSelection(this.imageToolSelectedStyle, this.imageToolAspect);
      return `${dims.width} x ${dims.height}`;
    },
    imageToolRefSlots() {
      const imgs = (this.composerImages || []).filter((r) => !r?.isDoc);
      return imgs.map((img, i) => ({
        token: `{image${i + 1}}`,
        name: String(img?.name || `image ${i + 1}`),
        previewUrl: String(img?.previewUrl || ""),
      }));
    },
    activeMessages() {
      return Array.isArray(this.activeConversation?.messages) ? this.activeConversation.messages : [];
    },
    activeMessagesWithDividers() {
      return this.withDayDividers(this.activeMessages);
    },
    waypointMessagesWithDividers() {
      return this.withDayDividers(Array.isArray(this.waypoint?.messages) ? this.waypoint.messages : []);
    },
    activeConversationSending() {
      const id = String(this.activeConversationId || "").trim();
      if (!id) {
        return false;
      }
      return Boolean(this.sendingByConversation[id]);
    },
    activeConversationSendingIsForaging() {
      const meta = this.conversationSendingMeta(this.activeConversationId);
      return Boolean(meta && meta.foraging);
    },
    activeConversationThinkingPhrase() {
      const phrases = [
        'Working on it.',
        'Thinking.',
        'One sec.',
        'Still here.',
      ];
      const idx = Math.floor((this.thinkingNowTs || Date.now()) / 4000) % phrases.length;
      return phrases[idx];
    },
    activeConversationForagingPhrase() {
      const phrases = [
        'Waking up the council.',
        'Deploying tiny robots.',
        'Loading the van.',
        'Calling in favors.',
      ];
      const idx = Math.floor((this.thinkingNowTs || Date.now()) / 4000) % phrases.length;
      return phrases[idx];
    },
    activeConversationElapsedSec() {
      const meta = this.conversationSendingMeta(this.activeConversationId);
      if (!meta) return 0;
      const started = Number(meta.startedAt || 0);
      if (!Number.isFinite(started) || started <= 0) return 0;
      const elapsedMs = Math.max(0, Number(this.thinkingNowTs || Date.now()) - started);
      return Math.floor(elapsedMs / 1000);
    },
    activeConversationCanCancel() {
      const meta = this.conversationSendingMeta(this.activeConversationId);
      if (!meta || !meta.requestId) return false;
      return !Boolean(meta.cancelRequested);
    },
    activeConversationSendingLabel() {
      const s = this.sendingJobStage[String(this.activeConversationId || "").trim()];
      return s ? String(s.label || "") : "";
    },
    activeConversationPendingEvents() {
      const convoId = String(this.activeConversationId || "").trim();
      const events = this.pendingJobEvents[convoId];
      const tracker = this.pendingJobAgentTracker[convoId];
      const rows = Array.isArray(events) ? events : [];
      return this._mergePendingEventsWithTracker(rows, tracker);
    },
    activeConversationLiveEvents() {
      const rows = Array.isArray(this.activeConversationPendingEvents)
        ? this.activeConversationPendingEvents
        : [];
      if (rows.length) {
        return rows;
      }
      const meta = this.conversationSendingMeta(this.activeConversationId);
      const startedAt = Number(meta?.startedAt || Date.now());
      const ts = new Date(Number.isFinite(startedAt) && startedAt > 0 ? startedAt : Date.now()).toISOString();
      return [{
        ts,
        stage: "waiting_for_events",
        detail: "Connecting to live stream...",
      }];
    },
    activeConversationQueuedTurns() {
      const id = String(this.activeConversationId || "").trim();
      if (!id) {
        return [];
      }
      const rows = this.queuedByConversation ? this.queuedByConversation[id] : [];
      return Array.isArray(rows) ? rows : [];
    },
    activeConversationQueueCount() {
      return this.activeConversationQueuedTurns.length;
    },
    activeTitle() {
      return String(this.activeConversation?.title || "Oathweaver");
    },
    watchtowerRows() {
      const rows = Array.isArray(this.panelData) && this.panelKey === "watchtower" ? this.panelData : [];
      return rows
        .map((row) => ({
          ...row,
          _schedule_label: this.watchScheduleLabel(row),
          _last_run_label: this.relativeTimeLabel(row?.last_run_at),
          _last_card_label: this.relativeTimeLabel(row?.last_card_at),
        }))
        .sort((a, b) => {
          const aEnabled = a?.enabled ? 0 : 1;
          const bEnabled = b?.enabled ? 0 : 1;
          if (aEnabled !== bEnabled) return aEnabled - bEnabled;
          const aUnread = Number(a?.unread_cards || 0);
          const bUnread = Number(b?.unread_cards || 0);
          if (aUnread !== bUnread) return bUnread - aUnread;
          return String(a?.created_at || "").localeCompare(String(b?.created_at || ""));
        });
    },
    watchtowerSummary() {
      const rows = this.watchtowerRows;
      const enabled = rows.filter((row) => Boolean(row?.enabled)).length;
      const unread = rows.reduce((sum, row) => sum + Number(row?.unread_cards || 0), 0);
      const totalCards = rows.reduce((sum, row) => sum + Number(row?.card_count || 0), 0);
      return {
        watch_count: rows.length,
        enabled_count: enabled,
        unread_count: unread,
        total_cards: totalCards,
      };
    },
    homeGreetingName() {
      return String(this.auth?.profile?.display_name || this.auth?.profile?.username || "there");
    },
    homeCompanionSketch() {
      const sketches = Array.isArray(this.homeCompanionSketches) ? this.homeCompanionSketches : [];
      if (!sketches.length) return null;
      const idx = Number(this.homeCompanionIndex || 0);
      const safeIndex = Number.isFinite(idx) && idx >= 0 ? idx % sketches.length : 0;
      return sketches[safeIndex] || sketches[0] || null;
    },
    homeCompanionDisplayName() {
      const value = String(this.homeCompanionName || "").trim();
      return value || HOME_COMPANION_DEFAULT_NAME;
    },
    homeCompanionStrokeColor() {
      return this.theme === "Day" ? "rgba(37, 58, 70, 0.92)" : "rgba(205, 228, 238, 0.9)";
    },
    homeTodayDateKey() {
      return toDateKey(startOfLocalDay(new Date()));
    },
    homeTodayLabel() {
      return startOfLocalDay(new Date()).toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      });
    },
    homeTodayEntries() {
      const key = String(this.homeTodayDateKey || "").trim();
      if (!key) {
        return [];
      }
      const idx = this.buildWaypointEventIndex(this.waypointCalendarEntries());
      const rows = Array.isArray(idx[key]) ? idx[key].slice() : [];
      rows.sort((a, b) => {
        // Rolled-over (overdue) tasks always float to the top
        const aRolled = a?.rolled_from_date ? 0 : 1;
        const bRolled = b?.rolled_from_date ? 0 : 1;
        if (aRolled !== bRolled) return aRolled - bRolled;
        const aTime = timeTextToMinutes(a?.start_time);
        const bTime = timeTextToMinutes(b?.start_time);
        if (aTime !== bTime) {
          return aTime - bTime;
        }
        const aTitle = String(a?.title || "").toLowerCase();
        const bTitle = String(b?.title || "").toLowerCase();
        if (aTitle < bTitle) {
          return -1;
        }
        if (aTitle > bTitle) {
          return 1;
        }
        return 0;
      });
      return rows;
    },
    homeTodayPreviewEntries() {
      return this.homeTodayEntries;
    },
    homeTodaySummaryLine() {
      const total = this.homeTodayEntries.length;
      const reminders = Number(this.waypoint?.open_reminders_count || 0);
      if (total <= 0 && reminders <= 0) {
        return "Nothing due yet. You're clear right now.";
      }
      const totalText = `${total} item${total === 1 ? "" : "s"} today`;
      if (reminders <= 0) {
        return totalText;
      }
      return `${totalText} • ${reminders} open reminder${reminders === 1 ? "" : "s"}`;
    },
    growthPanelBadgeCount() {
      return (Number(this.panelStatus?.pending_actions || 0) +
              Number(this.reflectionsUnreadCount || 0) +
              Number(this.lessonsUnreadCount || 0));
    },
    junctionPanelBadgeCount() {
      const values = [
        this.panelStatus?.pending_actions,
        this.reflectionsUnreadCount,
        this.lessonsUnreadCount,
        this.panelStatus?.library_items_pending,
        this.panelStatus?.topics_with_research,
        this.panelStatus?.cards_unread,
        this.panelStatus?.watchtower_active,
      ];
      return values.reduce((sum, value) => {
        const count = Number(value || 0);
        return sum + (Number.isFinite(count) && count > 0 ? Math.floor(count) : 0);
      }, 0);
    },
    agentGraphSummary() {
      const summary = this.agentGraphData && typeof this.agentGraphData === "object"
        ? this.agentGraphData.summary
        : {};
      return {
        active_jobs: Number(summary?.active_jobs || 0),
        foraging_jobs: Number(summary?.foraging_jobs || 0),
        building_jobs: Number(summary?.building_jobs || 0),
        active_agents: Number(summary?.active_agents || 0),
        foraging_active_agents: Number(summary?.foraging_active_agents || 0),
        building_active_agents: Number(summary?.building_active_agents || 0),
      };
    },
    agentGraphTransform() {
      const zoom = Number(this.agentGraphZoom || 1);
      const safeZoom = Number.isFinite(zoom) ? Math.max(AGENT_GRAPH_MIN_ZOOM, Math.min(AGENT_GRAPH_MAX_ZOOM, zoom)) : 1;
      const panX = Number(this.agentGraphPan?.x || 0);
      const panY = Number(this.agentGraphPan?.y || 0);
      return `translate(${panX} ${panY}) scale(${safeZoom})`;
    },
    agentGraphNodes() {
      const rows = Array.isArray(this.agentGraphData?.nodes) ? this.agentGraphData.nodes : [];
      const positions = this.agentGraphPositions && typeof this.agentGraphPositions === "object"
        ? this.agentGraphPositions
        : {};
      return rows.map((node) => {
        const id = String(node?.id || "").trim();
        const pos = positions[id] || {};
        const x = Number(pos.x);
        const y = Number(pos.y);
        return {
          ...(node || {}),
          id,
          x: Number.isFinite(x) ? x : 0,
          y: Number.isFinite(y) ? y : 0,
        };
      });
    },
    agentGraphEdgeSegments() {
      const out = [];
      const rows = Array.isArray(this.agentGraphData?.edges) ? this.agentGraphData.edges : [];
      const nodeMap = {};
      for (const node of this.agentGraphNodes) {
        const id = String(node?.id || "").trim();
        if (id) {
          nodeMap[id] = node;
        }
      }
      for (const edge of rows) {
        const sourceId = String(edge?.source || "").trim();
        const targetId = String(edge?.target || "").trim();
        const source = nodeMap[sourceId];
        const target = nodeMap[targetId];
        if (!source || !target) {
          continue;
        }
        const x1 = Number(source.x || 0), y1 = Number(source.y || 0);
        const x2 = Number(target.x || 0), y2 = Number(target.y || 0);
        const dx = x2 - x1, dy = y2 - y1;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
        const px = -dy / dist, py = dx / dist;
        const sag = dist * 0.16;
        const cpx = mx + px * sag * 0.3;
        const cpy = my + py * sag * 0.3 + sag * 0.6;
        out.push({
          source: sourceId,
          target: targetId,
          x1, y1, x2, y2,
          d: `M ${x1} ${y1} Q ${cpx} ${cpy} ${x2} ${y2}`,
          label: String(edge?.label || "").trim(),
        });
      }
      return out;
    },
    agentGraphSelectedNode() {
      const id = String(this.agentGraphSelectedNodeId || "").trim();
      if (!id) {
        return null;
      }
      return this.agentGraphNodes.find((node) => String(node?.id || "").trim() === id) || null;
    },
    overlayCloseVisible() {
      return Boolean(
        this.mdOverlayOpen ||
        this.actionsOverlayOpen ||
        this.panelOverlayOpen ||
        this.agentGraphModalOpen ||
        this.imageToolStyleModalOpen ||
        this.imageToolPromptModalOpen ||
        this.waypointTaskModalOpen ||
        this.waypointEventModalOpen ||
        this.waypointShoppingModalOpen ||
        this.waypointContactModalOpen ||
        this.projectPickerOpen ||
        this.projectBranchModalOpen ||
        this.projectTargetModalOpen ||
        this.projectTopicTypeModalOpen ||
        this.libraryIntakeOpen ||
        this.topicPickerOpen ||
        this.familyProfileModalOpen ||
        this.waypointMemberEditorOpen ||
        this.webPushModalOpen ||
        this.emailSettingsModalOpen ||
        this.botSettingsModalOpen ||
        this.resetModalOpen ||
        this.makeTypeModalOpen ||
        this.makeOutputEditModalOpen
      );
    },
    homeLastConversation() {
      const activeId = String(this.activeConversationId || "").trim();
      if (activeId) {
        const active = (Array.isArray(this.conversations) ? this.conversations : []).find(
          (row) => String(row?.id || "").trim() === activeId
        );
        if (active) {
          return active;
        }
      }
      const rows = Array.isArray(this.conversations) ? this.conversations : [];
      return rows.length ? rows[0] : null;
    },
    homeLastConversationUpdatedLabel() {
      const ts = String(this.homeLastConversation?.updated_at || "").trim();
      return this.formatLastActiveLabel(ts);
    },
    homeWeatherLocationDisplay() {
      const label = String(this.homeWeather?.locationLabel || "").trim();
      if (label) {
        return label;
      }
      const query = String(this.homeWeather?.locationQuery || "").trim();
      return query || "Set your weather location";
    },
    homeWeatherConditionLabel() {
      const code = Number(this.homeWeather?.weatherCode);
      if (!Number.isFinite(code)) {
        return "Weather unavailable";
      }
      return WEATHER_CODE_LABELS[code] || "Weather update";
    },
    homeWeatherEmoji() {
      const code = Number(this.homeWeather?.weatherCode);
      const isDay = Number(this.homeWeather?.isDay) === 1;
      if (!Number.isFinite(code)) {
        return "🌤️";
      }
      if (code === 0) {
        return isDay ? "☀️" : "🌙";
      }
      if (code <= 2) {
        return isDay ? "🌤️" : "☁️";
      }
      if (code === 3) {
        return "☁️";
      }
      if (code === 45 || code === 48) {
        return "🌫️";
      }
      if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) {
        return "🌧️";
      }
      if ((code >= 71 && code <= 77) || code === 85 || code === 86) {
        return "❄️";
      }
      if (code >= 95) {
        return "⛈️";
      }
      return "🌦️";
    },
    homeWeatherTempLabel() {
      const valueF = Number(this.homeWeather?.temperatureF);
      if (!Number.isFinite(valueF)) {
        return "--";
      }
      const valueC = Math.round(((valueF - 32) * 5) / 9);
      return `${Math.round(valueF)}°F / ${valueC}°C`;
    },
    homeWeatherCompactTemp() {
      const valueF = Number(this.homeWeather?.temperatureF);
      if (!Number.isFinite(valueF)) {
        return "--";
      }
      return `${Math.round(valueF)}°`;
    },
    homeWeatherHighLowLabel() {
      const high = Number(this.homeWeather?.highF);
      const low = Number(this.homeWeather?.lowF);
      if (!Number.isFinite(high) || !Number.isFinite(low)) {
        return "";
      }
      return `H ${Math.round(high)}° · L ${Math.round(low)}°`;
    },
    homeWeatherUpdatedLabel() {
      const raw = String(this.homeWeather?.updatedAt || "").trim();
      if (!raw) {
        return "";
      }
      const when = new Date(raw);
      if (Number.isNaN(when.getTime())) {
        return "";
      }
      return when.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      });
    },
    projectModeLabel() {
      return this.projectModeTitle(this.projectPipeline?.mode);
    },
    projectBuildTargetLabel() {
      return this.projectTargetTitle(this.projectPipeline?.target);
    },
    activeConversationProjectSlug() {
      const activeProject = String(this.activeConversation?.project || "").trim();
      return normalizeProjectSlug(activeProject || "general");
    },
    activeConversationIsProject() {
      const activeId = String(this.activeConversationId || "").trim();
      return Boolean(activeId) && this.activeConversationProjectSlug !== "general";
    },
    projectBuildTargetOptions() {
      return MAKE_TARGETS;
    },
    makeTargetLabel() {
      const r = MAKE_TARGETS.find((x) => x.value === (this.projectPipeline?.target || "auto"));
      return r ? r.label : "Auto";
    },
    isDiscoveryMode() {
      return (this.projectPipeline?.mode || "discovery") === "discovery";
    },
    isMakeMode() {
      return this.projectPipeline?.mode === "make";
    },
    topicFormValid() {
      return (
        String(this.topicForm.name || "").trim().length > 0 &&
        String(this.topicForm.type || "").trim().length > 0 &&
        String(this.topicForm.description || "").trim().length >= 50 &&
        String(this.topicForm.seed_question || "").trim().length > 0
      );
    },
    topicDescriptionCharCount() {
      return String(this.topicForm.description || "").trim().length;
    },
    filteredTopicPickerRows() {
      const q = String(this.topicPickerSearch || "").trim().toLowerCase();
      if (!q) return this.topicPickerRows;
      return this.topicPickerRows.filter(
        (t) =>
          String(t.name || "").toLowerCase().includes(q) ||
          String(t.type || "").toLowerCase().includes(q)
      );
    },
    sidebarTopicRowsEffective() {
      const preferred = Array.isArray(this.sidebarTopicRows) ? this.sidebarTopicRows : [];
      if (preferred.length) {
        return preferred;
      }
      return Array.isArray(this.topicPickerRows) ? this.topicPickerRows : [];
    },
    homeSortedTopics() {
      const topics = Array.isArray(this.sidebarTopicRowsEffective) ? this.sidebarTopicRowsEffective : [];
      return topics.slice().sort((a, b) => {
        const at = String(a?.last_research || a?.updated_at || a?.created_at || "");
        const bt = String(b?.last_research || b?.updated_at || b?.created_at || "");
        return bt.localeCompare(at);
      });
    },
    sidebarProjectHierarchy() {
      const projectRows = Array.isArray(this.sidebarProjectRows) ? this.sidebarProjectRows : [];
      const topics = Array.isArray(this.sidebarTopicRowsEffective) ? this.sidebarTopicRowsEffective : [];
      const conversations = Array.isArray(this.conversations) ? this.conversations : [];

      const topicById = new Map();
      const topicBySlug = new Map();
      for (const topic of topics) {
        const id = String(topic?.id || "").trim();
        const slug = normalizeProjectSlug(topic?.slug || topic?.name || "");
        if (id) {
          topicById.set(id, topic);
        }
        if (slug) {
          topicBySlug.set(slug, topic);
        }
      }

      const chatCountByProject = new Map();
      const recentConversationByProject = new Map();
      const topicHintByProject = new Map();
      for (const row of conversations) {
        const slug = normalizeProjectSlug(row?.project || "general");
        if (!slug || slug === "general") {
          continue;
        }
        chatCountByProject.set(slug, Number(chatCountByProject.get(slug) || 0) + 1);
        if (!recentConversationByProject.has(slug)) {
          recentConversationByProject.set(slug, row);
        }
        const rawTopicId = String(row?.topic_id || "").trim();
        if (rawTopicId && rawTopicId !== "general" && !topicHintByProject.has(slug)) {
          topicHintByProject.set(slug, rawTopicId);
        }
      }

      const projectMap = new Map();
      for (const row of projectRows) {
        const slug = normalizeProjectSlug(row?.project || "");
        if (!slug || slug === "general") {
          continue;
        }
        projectMap.set(slug, { ...row, project: slug });
      }
      for (const [slug, convo] of recentConversationByProject.entries()) {
        if (projectMap.has(slug)) {
          continue;
        }
        projectMap.set(slug, {
          project: slug,
          source: "conversation",
          updated_at: String(convo?.updated_at || convo?.created_at || "").trim(),
          research_summaries: 0,
          implementation_specs: 0,
          plan_docs: 0,
          event_count: 0,
          description: "",
          mode: "discovery",
          topic_type: "general",
        });
      }

      const typeOrder = new Map((Array.isArray(this.topicTypeOptions) ? this.topicTypeOptions : TOPIC_TYPES).map((row, idx) => [String(row?.value || "").trim().toLowerCase(), idx]));
      const rankType = (value) => {
        const key = String(value || "general").trim().toLowerCase() || "general";
        return typeOrder.has(key) ? Number(typeOrder.get(key)) : 10_000;
      };
      const parseTs = (value) => {
        const ts = Date.parse(String(value || "").trim());
        return Number.isFinite(ts) ? ts : 0;
      };

      const typeGroups = new Map();
      for (const [slug, row] of projectMap.entries()) {
        const hintedTopicId = String(topicHintByProject.get(slug) || "").trim();
        const topic = (hintedTopicId ? topicById.get(hintedTopicId) : null) || topicBySlug.get(slug) || null;
        const topicType = String(topic?.type || row?.topic_type || "general").trim().toLowerCase() || "general";
        const topicId = String(topic?.id || "").trim();
        const topicName = topic
          ? String(topic.name || slug).trim()
          : topicType === "general"
            ? "General / Unassigned"
            : `Unassigned ${this.topicTypeLabel(topicType)}`;
        const topicKey = topicId || `unassigned_${topicType}`;
        const chatCount = Number(chatCountByProject.get(slug) || 0);
        const recentConversation = recentConversationByProject.get(slug) || null;
        const projectItem = {
          project: slug,
          description: String(row?.description || "").trim(),
          updated_at: String(row?.updated_at || "").trim(),
          research_summaries: Number(row?.research_summaries || 0),
          implementation_specs: Number(row?.implementation_specs || 0),
          plan_docs: Number(row?.plan_docs || 0),
          event_count: Number(row?.event_count || 0),
          mode: String(row?.mode || "discovery").trim().toLowerCase() || "discovery",
          topic_type: topicType,
          topic_id: topicId,
          topic_name: topicName,
          chat_count: chatCount,
          latest_conversation_id: String(recentConversation?.id || "").trim(),
        };

        let typeGroup = typeGroups.get(topicType);
        if (!typeGroup) {
          typeGroup = {
            type: topicType,
            type_label: this.topicTypeLabel(topicType),
            topics_map: new Map(),
          };
          typeGroups.set(topicType, typeGroup);
        }
        let topicGroup = typeGroup.topics_map.get(topicKey);
        if (!topicGroup) {
          topicGroup = {
            id: topicId || topicKey,
            name: topicName,
            is_unassigned: !topicId,
            projects: [],
          };
          typeGroup.topics_map.set(topicKey, topicGroup);
        }
        topicGroup.projects.push(projectItem);
      }

      const groups = Array.from(typeGroups.values())
        .map((group) => {
          const topicsList = Array.from(group.topics_map.values())
            .map((topicGroup) => {
              topicGroup.projects.sort((a, b) => {
                const tsDiff = parseTs(b.updated_at) - parseTs(a.updated_at);
                if (tsDiff !== 0) {
                  return tsDiff;
                }
                const chatsDiff = Number(b.chat_count || 0) - Number(a.chat_count || 0);
                if (chatsDiff !== 0) {
                  return chatsDiff;
                }
                return String(a.project || "").localeCompare(String(b.project || ""));
              });
              const projectCount = topicGroup.projects.length;
              const chatCount = topicGroup.projects.reduce((sum, row) => sum + Number(row.chat_count || 0), 0);
              return {
                id: topicGroup.id,
                name: topicGroup.name,
                is_unassigned: topicGroup.is_unassigned,
                project_count: projectCount,
                chat_count: chatCount,
                projects: topicGroup.projects,
              };
            })
            .sort((a, b) => {
              if (a.is_unassigned !== b.is_unassigned) {
                return a.is_unassigned ? 1 : -1;
              }
              return String(a.name || "").localeCompare(String(b.name || ""));
            });
          const projectCount = topicsList.reduce((sum, item) => sum + Number(item.project_count || 0), 0);
          const chatCount = topicsList.reduce((sum, item) => sum + Number(item.chat_count || 0), 0);
          return {
            type: group.type,
            type_label: group.type_label,
            project_count: projectCount,
            chat_count: chatCount,
            topics: topicsList,
          };
        })
        .sort((a, b) => {
          const rankDiff = rankType(a.type) - rankType(b.type);
          if (rankDiff !== 0) {
            return rankDiff;
          }
          return String(a.type_label || "").localeCompare(String(b.type_label || ""));
        });
      return groups;
    },
    sidebarProjectCount() {
      return this.sidebarProjectHierarchy.reduce((sum, row) => sum + Number(row.project_count || 0), 0);
    },
    libraryPanelContext() {
      return this.panelData && typeof this.panelData === "object" && !Array.isArray(this.panelData)
        ? this.panelData
        : { items: [], counts: {}, topics: [], projects: [] };
    },
    libraryTopicOptions() {
      return Array.isArray(this.libraryPanelContext.topics) ? this.libraryPanelContext.topics : [];
    },
    libraryProjectOptions() {
      return Array.isArray(this.libraryPanelContext.projects) ? this.libraryPanelContext.projects : [];
    },
    filteredLibraryItems() {
      const ctx = this.libraryPanelContext;
      const rows = Array.isArray(ctx.items) ? ctx.items.slice() : [];
      const q = String(this.libraryFilter.search || "").trim().toLowerCase();
      const wantedStatus = String(this.libraryFilter.status || "all").trim().toLowerCase();
      const wantedKind = String(this.libraryFilter.kind || "all").trim().toLowerCase();
      const wantedTopic = String(this.libraryFilter.topic_id || "").trim();
      const wantedProject = String(this.libraryFilter.project_slug || "").trim().toLowerCase();
      return rows.filter((row) => {
        const title = String(row?.title || row?.source_name || "").toLowerCase();
        const kind = String(row?.source_kind || "").trim().toLowerCase();
        const status = String(row?.status || "").trim().toLowerCase();
        const topicId = String(row?.topic_id || "").trim();
        const projectSlug = String(row?.project_slug || "").trim().toLowerCase();
        if (q && !title.includes(q) && !String(row?.source_name || "").toLowerCase().includes(q)) {
          return false;
        }
        if (wantedStatus !== "all" && status !== wantedStatus) {
          return false;
        }
        if (wantedKind !== "all" && kind !== wantedKind) {
          return false;
        }
        if (wantedTopic && topicId !== wantedTopic) {
          return false;
        }
        if (wantedProject && projectSlug !== wantedProject) {
          return false;
        }
        return true;
      });
    },
    waypointSelectedDateLabel() {
      const parsed = parseDateKey(String(this.waypointSelectedDateKey || ""));
      const date = parsed || startOfLocalDay(this.waypointCalendarDate || new Date());
      return date.toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      });
    },
    waypointSelectedEntries() {
      const key = String(this.waypointSelectedDateKey || "").trim();
      if (!isIsoDate(key)) {
        return [];
      }
      const idx = this.buildWaypointEventIndex(this.waypointCalendarEntries());
      const rows = Array.isArray(idx[key]) ? idx[key].slice() : [];
      // Rolled-over tasks float to top, then by time
      rows.sort((a, b) => {
        const aRolled = a?.rolled_from_date ? 0 : 1;
        const bRolled = b?.rolled_from_date ? 0 : 1;
        if (aRolled !== bRolled) return aRolled - bRolled;
        return timeTextToMinutes(a?.start_time) - timeTextToMinutes(b?.start_time);
      });
      return rows;
    },
    waypointCalendarHasMemberFilters() {
      return this.normalizeWaypointMemberIds(this.waypointCalendarFilteredMemberIds || []).length > 0;
    },
    waypointCalendarFilterLabel() {
      const ids = this.normalizeWaypointMemberIds(this.waypointCalendarFilteredMemberIds || []);
      if (!ids.length) {
        return "All Members";
      }
      if (ids.length === 1) {
        const opt = (this.waypointMemberOptions || []).find((row) => String(row?.value || "") === ids[0]);
        return opt ? String(opt.label || "1 member") : "1 member";
      }
      return `${ids.length} members`;
    },
    waypointCanShowMonthPreview() {
      if (String(this.waypointCalendarView || "").trim().toLowerCase() !== "month") {
        return false;
      }
      const anchor = startOfLocalDay(this.waypointCalendarDate || new Date());
      const today = startOfLocalDay(new Date());
      return anchor.getFullYear() !== today.getFullYear() || anchor.getMonth() !== today.getMonth();
    },
    waypointMonthPreviewReport() {
      return this.buildWaypointMonthPreviewReport();
    },
    foragingStatusShort() {
      if (this.panelStatus.foraging_paused) {
        return "Research Paused";
      }
      const active = Number(this.panelStatus.foraging_active_jobs || 0);
      if (active > 0) {
        if (this.panelStatus.foraging_yielding) {
          return `Research Yielding (${active})`;
        }
        return `Research Active (${active})`;
      }
      if (this.panelStatus.foraging_yielding) {
        return "Research Yielding";
      }
      if (Boolean(this.panelStatus.foraging_completion_unread)) {
        return "Research Complete";
      }
      return "Research Ready";
    },
    foragingStatusTitle() {
      const active = Number(this.panelStatus.foraging_active_jobs || 0);
      const paused = Boolean(this.panelStatus.foraging_paused);
      const yielding = Boolean(this.panelStatus.foraging_yielding);
      return `Research status: ${paused ? "paused" : "running"} | active jobs: ${active} | yielding: ${
        yielding ? "yes" : "no"
      }`;
    },
    buildingStatusShort() {
      if (this.panelStatus.building_paused) {
        return "Building Paused";
      }
      const active = Number(this.panelStatus.building_active_jobs || 0);
      if (active > 0) {
        return `Building Active (${active})`;
      }
      if (Boolean(this.panelStatus.building_completion_unread)) {
        return "Building Complete";
      }
      return "Building Ready";
    },
    foragingPanelBadgeText() {
      const active = Number(this.panelStatus.foraging_active_jobs || 0);
      if (active > 0) {
        return "RUN";
      }
      if (Boolean(this.panelStatus.foraging_completion_unread)) {
        return "DONE";
      }
      return "";
    },
    foragingPanelBadgeClass() {
      if (this.foragingPanelBadgeText === "RUN") {
        return "is-status is-running";
      }
      if (this.foragingPanelBadgeText === "DONE") {
        return "is-status is-done";
      }
      return "";
    },
    buildingPanelBadgeText() {
      const active = Number(this.panelStatus.building_active_jobs || 0);
      if (active > 0) {
        return "RUN";
      }
      if (Boolean(this.panelStatus.building_completion_unread)) {
        return "DONE";
      }
      return "";
    },
    buildingPanelBadgeClass() {
      if (this.buildingPanelBadgeText === "RUN") {
        return "is-status is-running";
      }
      if (this.buildingPanelBadgeText === "DONE") {
        return "is-status is-done";
      }
      return "";
    },
    makeTypeCatalogCategories() {
      const cats = [];
      for (const entry of this.makeTypeCatalog) {
        if (!cats.includes(entry.category)) cats.push(entry.category);
      }
      return cats;
    },
    makeTypeCatalogByCategory() {
      const map = {};
      for (const entry of this.makeTypeCatalog) {
        if (!map[entry.category]) map[entry.category] = [];
        map[entry.category].push(entry);
      }
      return map;
    },
    panelTitle() {
      if (this.panelKey === "growth") {
        return "Growth";
      }
      if (this.panelKey === "foraging") {
        return "Research Control";
      }
      if (this.panelKey === "building") {
        return "Build Control";
      }
      if (this.panelKey === "reflections") {
        return "Reflection Moments";
      }
      if (this.panelKey === "lessons") {
        return "Guidance";
      }
      if (this.panelKey === "handoffs") {
        return "Handoffs";
      }
      if (this.panelKey === "outbox") {
        return "Outbox";
      }
      if (this.panelKey === "projects") {
        return "Topics";
      }
      if (this.panelKey === "project_detail") {
        return `Topic Detail: ${this.activeProject}`;
      }
      if (this.panelKey === "content") {
        return `Content: ${this.activeProject}`;
      }
      if (this.panelKey === "watchtower") {
        return "Watchtower";
      }
      if (this.panelKey === "library") {
        return "Library";
      }
      if (this.panelKey === "library_detail") {
        return this.libraryDetailItem ? `Library: ${this.libraryDetailItem.title || this.libraryDetailItem.source_name}` : "Library Detail";
      }
      if (this.panelKey === "topics") {
        return "Topics";
      }
      if (this.panelKey === "topic_detail") {
        return this.topicDetailData ? `Topic: ${this.topicDetailData.name}` : "Topic Detail";
      }
      if (this.panelKey === "system") {
        return "Settings";
      }
      return "Junction Panel";
    },
    panelSubtitle() {
      if (this.panelKey === "growth") {
        return "Postbag, Reflections, and Guidance in one place.";
      }
      if (this.panelKey === "foraging") {
        return "Background Research jobs, progress checkpoints, and quick controls.";
      }
      if (this.panelKey === "building") {
        return "Active Build jobs, stage progress, and quick controls.";
      }
      if (this.panelKey === "reflections") {
        return "Recent self-reflection blurbs with read/unread tracking.";
      }
      if (this.panelKey === "lessons") {
        return this.lessonsViewMode === "archive"
          ? "Archived guidance that is already approved."
          : "Current guidance that still needs review.";
      }
      if (this.panelKey === "handoffs") {
        return "Project handoff queue and ingest status.";
      }
      if (this.panelKey === "outbox") {
        return "Response files waiting for ingest or already processed.";
      }
      if (this.panelKey === "projects") {
        return "Per-project topic progress, artifacts, and routed lanes.";
      }
      if (this.panelKey === "project_detail") {
        return "Project-scoped topic artifacts, recent events, and handoff tasks.";
      }
      if (this.panelKey === "content") {
        return "Project file browser with collapsible folders and click-to-preview.";
      }
      if (this.panelKey === "watchtower") {
        return "Monitoring watches, run cadence, and watch-level signal health.";
      }
      if (this.panelKey === "library") {
        return "Private source documents, ingestion status, and reusable knowledge.";
      }
      if (this.panelKey === "library_detail") {
        return "Document metadata, summary, markdown preview, and source links.";
      }
      if (this.panelKey === "forage-cards") {
        return "Saved research cards from completed Research runs. Pin to keep.";
      }
      if (this.panelKey === "topics") {
        return "Topics — artifact counts, last activity, and mode.";
      }
      if (this.panelKey === "topic_detail") {
        return "Topic artifacts, sub-topics, and research history.";
      }
      if (this.panelKey === "system") {
        return "App preferences, global controls, and environment management.";
      }
      return "Live Junction status indicators.";
    },
    panelRows() {
      const rows = Array.isArray(this.panelData) ? [...this.panelData] : [];
      if (this.panelKey !== "lessons") {
        return rows;
      }

      const viewMode = String(this.lessonsViewMode || "current").trim().toLowerCase();
      const lessonRows = rows.filter((row) => {
        const status = String(row?.status || "").trim().toLowerCase();
        if (viewMode === "archive") {
          return status === "approved";
        }
        return status !== "approved";
      });
      const mode = String(this.lessonsSortBy || "newest").trim().toLowerCase();
      const collator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });
      const rowTs = (row) => {
        const raw = String((row && (row.created_at || row.updated_at || row.ts)) || "").trim();
        if (!raw) {
          return 0;
        }
        const parsed = Date.parse(raw);
        return Number.isFinite(parsed) ? parsed : 0;
      };
      const rowScore = (row) => {
        const n = Number((row && (row.confidence ?? row.score)) || 0);
        return Number.isFinite(n) ? n : 0;
      };
      const rowName = (row) => String((row && (row.principle || row.summary || row.id)) || "").trim();
      const rowProject = (row) => String((row && row.project) || "").trim();

      if (mode === "name") {
        lessonRows.sort((a, b) => {
          const cmp = collator.compare(rowName(a), rowName(b));
          if (cmp !== 0) {
            return cmp;
          }
          return rowTs(b) - rowTs(a);
        });
        if (this.lessonsFilterByTopic && this.activeProject) {
          return lessonRows.filter((r) => String(r.project || "").trim() === String(this.activeProject || "").trim());
        }
        return lessonRows;
      }

      if (mode === "project") {
        lessonRows.sort((a, b) => {
          const pcmp = collator.compare(rowProject(a), rowProject(b));
          if (pcmp !== 0) {
            return pcmp;
          }
          const ncmp = collator.compare(rowName(a), rowName(b));
          if (ncmp !== 0) {
            return ncmp;
          }
          return rowTs(b) - rowTs(a);
        });
        if (this.lessonsFilterByTopic && this.activeProject) {
          return lessonRows.filter((r) => String(r.project || "").trim() === String(this.activeProject || "").trim());
        }
        return lessonRows;
      }

      if (mode === "score") {
        lessonRows.sort((a, b) => {
          const diff = rowScore(b) - rowScore(a);
          if (diff !== 0) {
            return diff;
          }
          return rowTs(b) - rowTs(a);
        });
        if (this.lessonsFilterByTopic && this.activeProject) {
          return lessonRows.filter((r) => String(r.project || "").trim() === String(this.activeProject || "").trim());
        }
        return lessonRows;
      }

      lessonRows.sort((a, b) => {
        const diff = rowTs(b) - rowTs(a);
        if (diff !== 0) {
          return diff;
        }
        return rowScore(b) - rowScore(a);
      });
      if (this.lessonsFilterByTopic && this.activeProject) {
        return lessonRows.filter((r) => String(r.project || "").trim() === String(this.activeProject || "").trim());
      }
      return lessonRows;
    },
    waypointBuilderCommandOptions() {
      return [
        { value: "shopping_add", label: "Shopping: Add item" },
        { value: "shopping_complete", label: "Shopping: Mark complete" },
        { value: "shopping_delete", label: "Shopping: Delete item" },
        { value: "task_add", label: "Task: Add" },
        { value: "task_complete", label: "Task: Complete" },
        { value: "task_blocked", label: "Task: Blocked reason" },
        { value: "event_add", label: "Event: Add" },
        { value: "event_delete", label: "Event: Delete" },
        { value: "show_contacts", label: "Show contacts" },
        { value: "show_members", label: "Show members" },
        { value: "show_tasks", label: "Show tasks" },
        { value: "show_reminders", label: "Show reminders" },
        { value: "show_shopping", label: "Show shopping" },
        { value: "show_events", label: "Show events" },
        { value: "summary", label: "Summary" },
        { value: "help", label: "Help" },
      ];
    },
    waypointBuilderFields() {
      const cmd = String(this.waypointBuilder?.command || "").trim();
      if (cmd === "shopping_add") {
        return [
          {
            key: "shopping_category",
            label: "Category",
            type: "select",
            options: [
              { value: "food", label: "Grocery / Food" },
              { value: "general", label: "General" },
            ],
          },
          {
            key: "shopping_items",
            label: "Items",
            type: "textarea",
            placeholder: "milk, eggs, lettuce\nor one item per line",
          },
        ];
      }
      if (cmd === "shopping_complete" || cmd === "shopping_delete") {
        return [{ key: "shopping_id", label: "Shopping ID", type: "text", placeholder: "e.g. 855c09c2" }];
      }
      if (cmd === "task_add") {
        return [
          { key: "task_title", label: "Task title", type: "text", placeholder: "Fix sink, call doctor..." },
          { key: "task_due_date", label: "Due date", type: "date" },
          {
            key: "task_priority",
            label: "Priority",
            type: "select",
            options: [
              { value: "high", label: "High" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low" },
            ],
          },
        ];
      }
      if (cmd === "task_complete") {
        return [{ key: "task_id", label: "Task ID", type: "text", placeholder: "e.g. 41f5b773" }];
      }
      if (cmd === "task_blocked") {
        return [
          { key: "task_id", label: "Task ID", type: "text", placeholder: "e.g. 41f5b773" },
          { key: "task_reason", label: "Reason", type: "textarea", placeholder: "needed a wrench first" },
        ];
      }
      if (cmd === "event_add") {
        const locationOptions = [{ value: "", label: "Select saved host contact" }, ...this.waypointHostContactLocationOptions];
        return [
          { key: "event_title", label: "Event title", type: "text", placeholder: "Vet appointment" },
          { key: "event_date", label: "Date", type: "date" },
          { key: "event_start", label: "Start time", type: "time" },
          { key: "event_end", label: "End time", type: "time" },
          { key: "event_location_contact_id", label: "Host contact address", type: "select", options: locationOptions },
        ];
      }
      if (cmd === "event_delete") {
        return [{ key: "event_id", label: "Event ID", type: "text", placeholder: "e.g. 06bab024" }];
      }
      return [];
    },
    waypointContactKindOptions() {
      return [
        { value: "person", label: "Person" },
      ];
    },
    waypointContactRelationshipOptions() {
      return PLANNER_PERSON_RELATION_OPTIONS;
    },
    waypointMemberRelationshipOptions() {
      return PLANNER_PERSON_RELATION_OPTIONS;
    },
    waypointMemberEditorRelationshipOptions() {
      return PLANNER_PERSON_RELATION_OPTIONS;
    },
    waypointMemberRoleOptions() {
      return PLANNER_MEMBER_ROLE_OPTIONS;
    },
    waypointMemberOptions() {
      const rows = Array.isArray(this.waypoint?.members) ? this.waypoint.members : [];
      return rows
        .map((row) => {
          const id = String(row?.id || "").trim();
          if (!id) {
            return null;
          }
          const name = String(row?.name || row?.username || id).trim();
          return {
            value: id,
            label: name,
          };
        })
        .filter(Boolean);
    },
    waypointMemberColorMap() {
      const map = {};
      for (const m of (this.waypoint?.members || [])) {
        if (m.id) map[String(m.id)] = String(m.color || "").trim();
      }
      return map;
    },
    waypointContactLocationOptions() {
      const rows = Array.isArray(this.waypoint?.contact_locations) ? this.waypoint.contact_locations : [];
      const list = [];
      for (const row of rows) {
        const id = String(row?.id || "").trim();
        if (!id) {
          continue;
        }
        list.push({
          value: id,
          label: String(row?.label || row?.name || id).trim(),
          is_member: Boolean(row?.is_member),
          location: String(row?.location || "").trim(),
        });
      }
      return list;
    },
    waypointHostContactLocationOptions() {
      return this.waypointContactLocationOptions.filter((row) => !row.is_member);
    },
    waypointRecurrenceTypeOptions() {
      return [
        { value: "weekly_day", label: "By day (every Wednesday)" },
        { value: "monthly_nth_weekday", label: "By day ordinal (every 2nd Monday)" },
        { value: "monthly_day_of_month", label: "By date (every 15th)" },
      ];
    },
    waypointRecurrenceWeekdayOptions() {
      return [
        { value: 0, label: "Monday" },
        { value: 1, label: "Tuesday" },
        { value: 2, label: "Wednesday" },
        { value: 3, label: "Thursday" },
        { value: 4, label: "Friday" },
        { value: 5, label: "Saturday" },
        { value: 6, label: "Sunday" },
      ];
    },
    waypointRecurrenceNthOptions() {
      return [
        { value: 1, label: "1st" },
        { value: 2, label: "2nd" },
        { value: 3, label: "3rd" },
        { value: 4, label: "4th" },
        { value: 5, label: "Last" },
      ];
    },
    waypointBuilderPreview() {
      return this.buildWaypointCommandFromBuilder();
    },
    projectPickerFilteredRows() {
      const rows = Array.isArray(this.projectPickerRows) ? this.projectPickerRows : [];
      const query = String(this.projectPickerSearch || "").trim().toLowerCase();
      if (!query) {
        return rows;
      }
      return rows.filter((row) => {
        const project = String(row?.project || "").trim().toLowerCase();
        const description = String(row?.description || "").trim().toLowerCase();
        return project.includes(query) || description.includes(query);
      });
    },
    projectBranchFilteredRows() {
      const rows = Array.isArray(this.projectPickerRows) ? this.projectPickerRows : [];
      const query = String(this.projectBranchSearch || "").trim().toLowerCase();
      if (!query) {
        return rows;
      }
      return rows.filter((row) => {
        const project = String(row?.project || "").trim().toLowerCase();
        const description = String(row?.description || "").trim().toLowerCase();
        return project.includes(query) || description.includes(query);
      });
    },
    webPushPermissionLabel() {
      const permission = String(this.webPushPermission || "default").trim().toLowerCase();
      if (permission === "granted") {
        return "Allowed";
      }
      if (permission === "denied") {
        return "Blocked in browser settings";
      }
      return "Not requested yet";
    },
    webPushLastError() {
      return String(this.webPushSettings?.last_error || "").trim();
    },
    webPushStatusLine() {
      if (!supportsWebPushClient()) {
        return "This browser context cannot use Web Push. Use HTTPS or install the app first.";
      }
      if (!this.webPushSettings.server_supported) {
        return "Server-side Web Push is not ready yet.";
      }
      if (this.webPushSettings.has_subscription) {
        return "This device is subscribed and can receive Oathweaver notifications.";
      }
      return "This device is not subscribed yet.";
    },
    webPushInstallLine() {
      if (isProbablyIosDevice() && !this.webPushInstalled) {
        return "On iPhone, open this site in Safari, use Share -> Add to Home Screen, then launch the installed web app and enable notifications there.";
      }
      if (!window.isSecureContext) {
        return "Web Push requires HTTPS, except on localhost.";
      }
      return "";
    },
  },

  watch: {
    "topicForm.type"(val) {
      this.topicFormUndergroundWarning = String(val || "").trim().toLowerCase() === "underground";
    },
    activeConversationSending(val) {
      if (val) {
        this.closeBlockingOverlaysForStreaming();
      }
    },
    activeConversation: {
      handler(val) {
        this.syncCompletedThinkStreamsFromConversation(val);
      },
      deep: false,
    },
    sendingByConversation: {
      handler(val) {
        try {
          sessionStorage.setItem("oathweaver_pending_jobs", JSON.stringify(val || {}));
        } catch (_e) {}
      },
      deep: true,
    },
  },

  methods: {
    refreshWebPushClientState() {
      this.webPushPermission = "Notification" in window ? String(Notification.permission || "default") : "default";
      this.webPushInstalled = isInstalledWebApp();
      this.webPushRegistrationReady = Boolean(this._webPushRegistration);
    },

    async initializeWebPushSupport() {
      this.refreshWebPushClientState();
      if (!supportsWebPushClient()) {
        return;
      }
      try {
        const registration = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
        this._webPushRegistration = registration;
        this.webPushRegistrationReady = true;
      } catch (err) {
        console.warn("Service worker registration failed:", err);
      } finally {
        this.refreshWebPushClientState();
      }
    },

    async getWebPushRegistration() {
      if (this._webPushRegistration) {
        return this._webPushRegistration;
      }
      if (!supportsWebPushClient()) {
        return null;
      }
      try {
        const registration = await navigator.serviceWorker.ready;
        this._webPushRegistration = registration;
        this.webPushRegistrationReady = true;
        return registration;
      } catch (_err) {
        return null;
      }
    },

    async refreshWebPushSettings() {
      this.refreshWebPushClientState();
      if (this.auth.enabled && !this.auth.authenticated) {
        this.webPushSettings = {
          server_supported: false,
          public_key: "",
          vapid_subject: "",
          enabled: true,
          subscription_count: 0,
          has_subscription: false,
          last_error: "",
          last_test_sent_at: "",
        };
        return;
      }
      try {
        const payload = await this.apiGet("/api/settings/web-push");
        this.webPushSettings = {
          server_supported: Boolean(payload.server_supported),
          public_key: String(payload.public_key || "").trim(),
          vapid_subject: String(payload.vapid_subject || "").trim(),
          enabled: Boolean(payload.enabled),
          subscription_count: Number(payload.subscription_count || 0),
          has_subscription: Boolean(payload.has_subscription),
          last_error: String(payload.last_error || "").trim(),
          last_test_sent_at: String(payload.last_test_sent_at || "").trim(),
        };
      } catch (err) {
        this.webPushSettings = {
          server_supported: false,
          public_key: "",
          vapid_subject: "",
          enabled: true,
          subscription_count: 0,
          has_subscription: false,
          last_error: String(err.message || err),
          last_test_sent_at: "",
        };
      }
    },

    openWebPushSettingsModal() {
      this.chatMenuOpen = false;
      this.webPushModalOpen = true;
      this.updateBodyClasses();
      this.refreshWebPushSettings();
    },

    closeWebPushSettingsModal() {
      this.webPushModalOpen = false;
      this.updateBodyClasses();
    },

    async enableWebPush() {
      this.webPushSubmitting = true;
      try {
        this.refreshWebPushClientState();
        if (!supportsWebPushClient()) {
          throw new Error("This browser does not currently support Web Push in this context.");
        }
        if (isProbablyIosDevice() && !this.webPushInstalled) {
          throw new Error("On iPhone, add Oathweaver to your Home Screen first, then open the installed web app and try again.");
        }
        const registration = await this.getWebPushRegistration();
        if (!registration) {
          throw new Error("Service worker registration is not ready yet.");
        }
        await this.refreshWebPushSettings();
        const publicKey = String(this.webPushSettings.public_key || "").trim();
        if (!this.webPushSettings.server_supported || !publicKey) {
          throw new Error(this.webPushLastError || "Server-side Web Push is not configured.");
        }
        const permission = await Notification.requestPermission();
        this.webPushPermission = permission;
        if (permission !== "granted") {
          throw new Error("Notification permission was not granted.");
        }
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
          });
        }
        await this.apiPost("/api/settings/web-push/subscribe", {
          installed: this.webPushInstalled,
          subscription: subscription.toJSON(),
        });
        await this.refreshWebPushSettings();
      } catch (err) {
        window.alert(String(err.message || err));
      } finally {
        this.webPushSubmitting = false;
        this.refreshWebPushClientState();
      }
    },

    async disableWebPush() {
      this.webPushSubmitting = true;
      try {
        const registration = await this.getWebPushRegistration();
        let endpoint = "";
        if (registration) {
          const subscription = await registration.pushManager.getSubscription();
          endpoint = String(subscription?.endpoint || "").trim();
          if (subscription) {
            try {
              await subscription.unsubscribe();
            } catch (_err) {}
          }
        }
        if (!endpoint) {
          throw new Error("Could not find a subscription for this device.");
        }
        await this.apiPost("/api/settings/web-push/unsubscribe", { endpoint });
        await this.refreshWebPushSettings();
      } catch (err) {
        window.alert("Could not disable push: " + String(err.message || err));
      } finally {
        this.webPushSubmitting = false;
      }
    },

    async testWebPushSettings() {
      this.webPushSubmitting = true;
      try {
        await this.apiPost("/api/settings/web-push/test", {});
        window.alert("Test push queued. Check this device.");
        await this.refreshWebPushSettings();
      } catch (err) {
        window.alert("Push test failed: " + String(err.message || err));
      } finally {
        this.webPushSubmitting = false;
      }
    },

    async markConversationRead(conversationId, options = {}) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return null;
      }
      try {
        const payload = await this.apiPost(`/api/conversations/${encodeURIComponent(id)}/read`, {});
        const convo = payload && payload.conversation ? payload.conversation : null;
        if (convo && String(this.activeConversationId || "").trim() === id) {
          this.activeConversation = convo;
        }
        if (options.refreshList !== false) {
          await this.refreshConversations();
        }
        return convo;
      } catch (_err) {
        return null;
      }
    },

    saveDraftForConversation(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const next = Object.assign({}, this.conversationDrafts || {});
      const text = String(this.draft || "");
      if (text.trim()) {
        next[id] = text;
      } else {
        delete next[id];
      }
      this.conversationDrafts = next;
    },

    restoreDraftForConversation(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        this.draft = "";
        return;
      }
      const saved = this.conversationDrafts && typeof this.conversationDrafts === "object"
        ? this.conversationDrafts[id]
        : "";
      this.draft = String(saved || "");
    },

    clearDraftForConversation(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const next = Object.assign({}, this.conversationDrafts || {});
      if (Object.prototype.hasOwnProperty.call(next, id)) {
        delete next[id];
        this.conversationDrafts = next;
      }
      if (String(this.activeConversationId || "").trim() === id) {
        this.draft = "";
      }
    },

    releaseComposerImagePreviews(rows, seen = null) {
      const list = Array.isArray(rows) ? rows : [];
      const visited = seen instanceof Set ? seen : new Set();
      for (const row of list) {
        const url = String(row?.previewUrl || "").trim();
        if (!url || visited.has(url)) {
          continue;
        }
        visited.add(url);
        try {
          URL.revokeObjectURL(url);
        } catch (_err) {}
      }
      return visited;
    },

    saveComposerStateForConversation(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const next = Object.assign({}, this.conversationComposerState || {});
      const images = Array.isArray(this.composerImages) ? this.composerImages.slice() : [];
      const replyTarget = this.replyTargetMsg && typeof this.replyTargetMsg === "object"
        ? Object.assign({}, this.replyTargetMsg)
        : null;
      if (!images.length && !replyTarget) {
        delete next[id];
      } else {
        next[id] = {
          images,
          replyTarget,
        };
      }
      this.conversationComposerState = next;
    },

    restoreComposerStateForConversation(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        this.composerImages = [];
        this.replyTargetMsg = null;
        return;
      }
      const row = this.conversationComposerState && typeof this.conversationComposerState === "object"
        ? this.conversationComposerState[id]
        : null;
      this.composerImages = Array.isArray(row?.images) ? row.images.slice() : [];
      this.replyTargetMsg = row?.replyTarget && typeof row.replyTarget === "object"
        ? Object.assign({}, row.replyTarget)
        : null;
    },

    clearComposerStateForConversation(conversationId, options = {}) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const releaseAssets = options?.releaseAssets !== false;
      const activeId = String(this.activeConversationId || "").trim();
      const savedRow = this.conversationComposerState && typeof this.conversationComposerState === "object"
        ? this.conversationComposerState[id]
        : null;
      const savedImages = Array.isArray(savedRow?.images) ? savedRow.images : [];
      const activeImages = activeId === id && Array.isArray(this.composerImages) ? this.composerImages : [];
      if (releaseAssets) {
        const seen = this.releaseComposerImagePreviews(savedImages);
        this.releaseComposerImagePreviews(activeImages, seen);
      }
      const next = Object.assign({}, this.conversationComposerState || {});
      if (Object.prototype.hasOwnProperty.call(next, id)) {
        delete next[id];
        this.conversationComposerState = next;
      }
      if (activeId === id) {
        this.composerImages = [];
        this.replyTargetMsg = null;
        const imageInput = this.$refs.imageInput;
        if (imageInput) {
          imageInput.value = "";
        }
        const fileInput = this.$refs.fileInput;
        if (fileInput) {
          fileInput.value = "";
        }
      }
    },

    conversationSendingMeta(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return null;
      }
      const row = this.sendingByConversation ? this.sendingByConversation[id] : null;
      if (!row) {
        return null;
      }
      if (typeof row === "object") {
        return row;
      }
      return {
        requestId: "",
        startedAt: Date.now(),
        cancelRequested: false,
        foraging: false,
      };
    },

    isConversationSending(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return false;
      }
      return Boolean(this.conversationSendingMeta(id));
    },

    setConversationSending(conversationId, value) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const next = Object.assign({}, this.sendingByConversation || {});
      if (value) {
        if (typeof value === "object") {
          next[id] = {
            requestId: String(value.requestId || "").trim(),
            startedAt: Number(value.startedAt || Date.now()),
            cancelRequested: Boolean(value.cancelRequested),
            foraging: Boolean(value.foraging),
            renderJob: Boolean(value.renderJob),
          };
        } else {
          next[id] = {
            requestId: "",
            startedAt: Date.now(),
            cancelRequested: false,
            foraging: false,
            renderJob: false,
          };
        }
      } else {
        delete next[id];
        const nextStage = Object.assign({}, this.sendingJobStage);
        delete nextStage[id];
        this.sendingJobStage = nextStage;
        const nextEvents = Object.assign({}, this.pendingJobEvents);
        delete nextEvents[id];
        this.pendingJobEvents = nextEvents;
        const nextTracker = Object.assign({}, this.pendingJobAgentTracker);
        delete nextTracker[id];
        this.pendingJobAgentTracker = nextTracker;
        const nextSources = Object.assign({}, this.pendingLiveSources);
        delete nextSources[id];
        this.pendingLiveSources = nextSources;
      }
      this.sendingByConversation = next;
    },

    conversationQueue(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return [];
      }
      const rows = this.queuedByConversation ? this.queuedByConversation[id] : [];
      return Array.isArray(rows) ? rows : [];
    },

    setConversationQueue(conversationId, rows) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const next = Object.assign({}, this.queuedByConversation || {});
      const safeRows = Array.isArray(rows) ? rows.filter((row) => row && typeof row === "object") : [];
      if (safeRows.length) {
        next[id] = safeRows;
      } else {
        delete next[id];
      }
      this.queuedByConversation = next;
    },

    releaseQueuedMessageAssets(item) {
      const imageRows = Array.isArray(item?.imageRows) ? item.imageRows : [];
      for (const row of imageRows) {
        if (row?.previewUrl) {
          URL.revokeObjectURL(row.previewUrl);
        }
      }
    },

    buildQueuedMessageItem({
      conversationId,
      content,
      imageRows,
      selectedLoras,
      imageStyle,
      mode,
      replyTarget,
    }) {
      let id = "";
      try {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          id = String(window.crypto.randomUUID());
        }
      } catch (_err) {}
      if (!id) {
        id = `queued_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      }
      const text = String(content || "").trim();
      const files = Array.isArray(imageRows) ? imageRows.slice() : [];
      const loras = this.normalizeLoraSelection(selectedLoras);
      const resolvedImageStyle = String(imageStyle || "").trim() || (loras.length ? "lora" : "realistic");
      return {
        id,
        conversationId: String(conversationId || "").trim(),
        content: text,
        imageRows: files,
        selectedLoras: loras,
        imageStyle: resolvedImageStyle,
        mode: String(mode || "talk").trim() || "talk",
        replyTarget: replyTarget && typeof replyTarget === "object" ? Object.assign({}, replyTarget) : null,
        queuedAt: Date.now(),
      };
    },

    queuedMessageModeLabel(item) {
      const mode = String(item?.mode || "").trim().toLowerCase();
      if (mode === "forage") return "Research";
      if (mode === "make") return "Make";
      if (mode === "plan") return "Plan";
      return "Talk";
    },

    queuedMessageExcerpt(item) {
      const text = String(item?.content || "").trim();
      const attachmentCount = Array.isArray(item?.imageRows) ? item.imageRows.length : 0;
      if (text) {
        return text.length > 140 ? `${text.slice(0, 140).trim()}...` : text;
      }
      if (attachmentCount > 0) {
        return `${attachmentCount} attachment${attachmentCount === 1 ? "" : "s"}`;
      }
      return "Queued turn";
    },

    queueComposerMessage() {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return false;
      }
      const typedContent = String(this.draft || "").trim();
      const imageRows = Array.isArray(this.composerImages) ? this.composerImages.slice() : [];
      if (!typedContent && imageRows.length === 0) {
        return false;
      }
      const selectedLoras = this.normalizeLoraSelection(this.composerSelectedLoras);
      const sendMode = this.inputMode === "forage"
        ? "forage"
        : (this.inputMode === "make" ? "make" : (this.inputMode === "plan" ? "plan" : "talk"));
      const item = this.buildQueuedMessageItem({
        conversationId,
        content: typedContent,
        imageRows,
        selectedLoras,
        imageStyle: selectedLoras.length ? "lora" : "realistic",
        mode: sendMode,
        replyTarget: this.replyTargetMsg || null,
      });
      const next = this.conversationQueue(conversationId).slice();
      next.push(item);
      this.setConversationQueue(conversationId, next);
      this.draft = "";
      this.saveDraftForConversation(conversationId);
      this.composerImages = [];
      this.replyTargetMsg = null;
      this.saveComposerStateForConversation(conversationId);
      this.composerAddMenuOpen = false;
      if (this.$refs.imageInput) {
        this.$refs.imageInput.value = "";
      }
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = "";
      }
      this.resizeComposer();
      this.$nextTick(() => {
        const node = this.$refs.composerInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
      return true;
    },

    removeQueuedMessage(itemId) {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return;
      }
      const queue = this.conversationQueue(conversationId);
      const idx = queue.findIndex((row) => String(row?.id || "") === String(itemId || ""));
      if (idx < 0) {
        return;
      }
      this.releaseQueuedMessageAssets(queue[idx]);
      const next = queue.slice();
      next.splice(idx, 1);
      this.setConversationQueue(conversationId, next);
    },

    editQueuedMessage(itemId) {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return;
      }
      const queue = this.conversationQueue(conversationId);
      const idx = queue.findIndex((row) => String(row?.id || "") === String(itemId || ""));
      if (idx < 0) {
        return;
      }
      const item = queue[idx];
      const next = queue.slice();
      next.splice(idx, 1);
      this.setConversationQueue(conversationId, next);
      this.draft = String(item?.content || "");
      this.composerImages = Array.isArray(item?.imageRows) ? item.imageRows.slice() : [];
      this.composerSelectedLoras = this.normalizeLoraSelection(item?.selectedLoras || []);
      this.composerImageStyle = String(item?.imageStyle || "").trim() || (this.composerSelectedLoras.length ? "lora" : "realistic");
      this.replyTargetMsg = item?.replyTarget && typeof item.replyTarget === "object" ? Object.assign({}, item.replyTarget) : null;
      this.inputMode = String(item?.mode || "talk").trim() || "talk";
      this.composerAddMenuOpen = false;
      this.saveDraftForConversation(conversationId);
      this.saveComposerStateForConversation(conversationId);
      this.$nextTick(() => {
        this.resizeComposer();
        const node = this.$refs.composerInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    promoteQueuedMessage(itemId) {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return;
      }
      const queue = this.conversationQueue(conversationId);
      const idx = queue.findIndex((row) => String(row?.id || "") === String(itemId || ""));
      if (idx <= 0) {
        return;
      }
      const next = queue.slice();
      const [item] = next.splice(idx, 1);
      next.unshift(item);
      this.setConversationQueue(conversationId, next);
    },

    async runQueuedMessageNow(itemId) {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return false;
      }
      this.promoteQueuedMessage(itemId);
      if (this.isConversationSending(conversationId)) {
        return true;
      }
      return this.flushConversationQueue(conversationId);
    },

    async flushConversationQueue(conversationId) {
      const id = String(conversationId || "").trim();
      if (!id || this.isConversationSending(id)) {
        return false;
      }
      const queue = this.conversationQueue(id);
      if (!queue.length) {
        return false;
      }
      const [item, ...rest] = queue;
      this.setConversationQueue(id, rest);
      const ok = await this.sendMessage(item);
      if (!ok) {
        this.setConversationQueue(id, [item, ...this.conversationQueue(id)]);
      }
      return ok;
    },

    isMobileLayout() {
      return window.matchMedia("(max-width: 980px)").matches;
    },

    panelBadgeValue(rawCount) {
      const count = Number(rawCount || 0);
      if (!Number.isFinite(count) || count <= 0) {
        return "";
      }
      return String(Math.max(1, Math.floor(count)));
    },

    laneJobIsCancelable(row) {
      const status = String(row?.status || "").trim().toLowerCase();
      return status === "running";
    },

    lessonsStorageKey() {
      const profileId = String(this.auth?.profile?.id || "anon").trim() || "anon";
      return `oathweaver_lessons_read_${profileId}`;
    },

    reflectionsStorageKey() {
      const profileId = String(this.auth?.profile?.id || "anon").trim() || "anon";
      return `oathweaver_reflections_read_${profileId}`;
    },

    loadLessonReadState() {
      let next = {};
      try {
        const raw = localStorage.getItem(this.lessonsStorageKey());
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            next = parsed;
          }
        }
      } catch (_err) {
        next = {};
      }
      this.lessonsReadIds = next;
    },

    loadReflectionReadState() {
      let next = {};
      try {
        const raw = localStorage.getItem(this.reflectionsStorageKey());
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            next = parsed;
          }
        }
      } catch (_err) {
        next = {};
      }
      this.reflectionsReadIds = next;
    },

    saveLessonReadState() {
      try {
        localStorage.setItem(this.lessonsStorageKey(), JSON.stringify(this.lessonsReadIds || {}));
      } catch (_err) {}
    },

    saveReflectionReadState() {
      try {
        localStorage.setItem(this.reflectionsStorageKey(), JSON.stringify(this.reflectionsReadIds || {}));
      } catch (_err) {}
    },

    markLessonsAsRead(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) {
        return;
      }
      const map = Object.assign({}, this.lessonsReadIds || {});
      let changed = false;
      for (const row of list) {
        const id = String(row?.id || "").trim();
        if (!id) {
          continue;
        }
        if (!map[id]) {
          map[id] = 1;
          changed = true;
        }
      }
      if (!changed) {
        this.lessonsUnreadCount = 0;
        return;
      }
      this.lessonsReadIds = map;
      this.lessonsUnreadCount = 0;
      this.saveLessonReadState();
    },

    markReflectionsAsRead(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) {
        return;
      }
      const map = Object.assign({}, this.reflectionsReadIds || {});
      let changed = false;
      for (const row of list) {
        const id = String(row?.id || "").trim();
        if (!id) {
          continue;
        }
        if (!map[id]) {
          map[id] = 1;
          changed = true;
        }
      }
      if (!changed) {
        this.reflectionsUnreadCount = 0;
        return;
      }
      this.reflectionsReadIds = map;
      this.reflectionsUnreadCount = 0;
      this.saveReflectionReadState();
    },

    reflectionIsRead(row) {
      const id = String(row?.id || "").trim();
      if (!id) {
        return true;
      }
      return Boolean((this.reflectionsReadIds || {})[id]);
    },

    toggleReflectionRead(row) {
      const id = String(row?.id || "").trim();
      if (!id) {
        return;
      }
      const map = Object.assign({}, this.reflectionsReadIds || {});
      if (map[id]) {
        delete map[id];
      } else {
        map[id] = 1;
      }
      this.reflectionsReadIds = map;
      this.saveReflectionReadState();
      this.refreshReflectionsUnreadCount(true);
    },

    async refreshLessonsUnreadCount(force = false) {
      const now = Date.now();
      if (!force && now - Number(this.lessonsUnreadCheckedAt || 0) < 30000) {
        return;
      }
      this.lessonsUnreadCheckedAt = now;
      try {
        const payload = await this.apiGet("/api/panel/lessons?limit=200");
        const rows = Array.isArray(payload.lessons) ? payload.lessons : [];
        const readMap = this.lessonsReadIds || {};
        let unread = 0;
        for (const row of rows) {
          const id = String(row?.id || "").trim();
          if (!id) {
            continue;
          }
          if (!readMap[id]) {
            unread += 1;
          }
        }
        this.lessonsUnreadCount = unread;
      } catch (_err) {
        this.lessonsUnreadCount = Number(this.panelStatus.learned_lessons || 0);
      }
    },

    async refreshReflectionsUnreadCount(force = false) {
      const now = Date.now();
      if (!force && now - Number(this.reflectionsUnreadCheckedAt || 0) < 30000) {
        return;
      }
      this.reflectionsUnreadCheckedAt = now;
      try {
        const payload = await this.apiGet("/api/panel/reflections-history?limit=300");
        const rows = Array.isArray(payload.reflections) ? payload.reflections : [];
        const readMap = this.reflectionsReadIds || {};
        let unread = 0;
        for (const row of rows) {
          const id = String(row?.id || "").trim();
          if (!id) {
            continue;
          }
          if (!readMap[id]) {
            unread += 1;
          }
        }
        this.reflectionsUnreadCount = unread;
      } catch (_err) {
        this.reflectionsUnreadCount = Number(this.panelStatus.open_reflections || 0);
      }
    },

    reflectionMomentTitle(row) {
      const summary = String(row?.summary || "").trim();
      if (summary) {
        return summary.length > 88 ? `${summary.slice(0, 85)}...` : summary;
      }
      return String(row?.question_for_user || "Reflection moment");
    },

    reflectionMomentBlurb(row) {
      const improve = Array.isArray(row?.what_to_improve) ? row.what_to_improve : [];
      const firstImprove = String(improve[0] || "").trim();
      const experiment = String(row?.next_experiment || "").trim();
      const question = String(row?.question_for_user || "").trim();
      const parts = [];
      if (firstImprove) {
        parts.push(`Realized: ${firstImprove}`);
      }
      if (experiment) {
        parts.push(`Changed approach: ${experiment}`);
      }
      if (question) {
        parts.push(`Check-in prompt: ${question}`);
      }
      if (parts.length === 0) {
        return String(row?.summary || "Reflection logged.");
      }
      return parts.join(" ");
    },

    lessonSummary(row) {
      return String(row?.summary || row?.principle || "Lesson").trim();
    },

    lessonConfidenceValue(row) {
      const value = Number(row?.confidence ?? row?.score ?? 0);
      return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    },

    lessonConfidenceText(row) {
      const value = this.lessonConfidenceValue(row);
      return `${value.toFixed(2)} (${Math.round(value * 100)}%)`;
    },

    lessonConfidenceClass(row) {
      const value = this.lessonConfidenceValue(row);
      if (value >= 0.8) return "is-high";
      if (value >= 0.6) return "is-medium";
      return "is-low";
    },

    lessonStatusText(row) {
      const value = String(row?.status || "").trim().toLowerCase();
      if (!value) return "candidate";
      return value.replace(/_/g, " ");
    },

    lessonStatusClass(row) {
      const value = String(row?.status || "").trim().toLowerCase();
      if (value === "approved") return "is-approved";
      if (value === "candidate") return "is-candidate";
      if (value === "rejected") return "is-rejected";
      if (value === "expired") return "is-expired";
      return "is-neutral";
    },

    lessonOriginText(row) {
      const value = String(row?.origin_type || row?.source || "").trim().toLowerCase();
      return value ? value.replace(/_/g, " ") : "unknown";
    },

    lessonGuidanceLines(row) {
      const raw = String(row?.guidance || row?.trigger || "").replace(/\r\n/g, "\n").trim();
      if (!raw) return [];
      const lines = raw
        .split("\n")
        .map((line) => String(line || "").trim())
        .filter((line) => line.length > 0)
        .map((line) => line.replace(/^\-\s+/, ""));
      if (lines.length > 1) {
        return lines.slice(0, 3);
      }
      const sentenceParts = lines[0]
        .split(/(?<=[.!?])\s+/)
        .map((line) => String(line || "").trim())
        .filter((line) => line.length > 0);
      return (sentenceParts.length ? sentenceParts : lines).slice(0, 3);
    },

    lessonCanApprove(row) {
      const status = String(row?.status || "").trim().toLowerCase() || "candidate";
      return status === "candidate";
    },

    lessonCanReject(row) {
      const status = String(row?.status || "").trim().toLowerCase() || "candidate";
      return status === "candidate" || status === "approved";
    },

    lessonCanExpire(row) {
      const status = String(row?.status || "").trim().toLowerCase() || "candidate";
      return status === "approved";
    },

    toggleLessonsView() {
      if (this.panelKey !== "lessons") {
        return;
      }
      this.lessonsViewMode = this.lessonsViewMode === "archive" ? "current" : "archive";
    },

    async applyLessonAction(row, action) {
      const id = String(row?.id || "").trim();
      const verb = String(action || "").trim().toLowerCase();
      if (!id || !["approve", "reject", "expire"].includes(verb)) {
        return;
      }
      try {
        const endpoint = `/api/lessons/${encodeURIComponent(id)}/${verb}`;
        const payload = await this.apiPost(endpoint, {});
        if (!payload?.ok) {
          throw new Error(String(payload?.message || "Lesson action failed."));
        }
        await this.refreshSystemPanel();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Lesson update failed: ${String(err.message || err)}`);
      }
    },

    syncViewportHeight() {
      const viewport = window.visualViewport;
      const innerHeight = Math.round(window.innerHeight || document.documentElement.clientHeight || 0);
      const visualHeight = Math.round(viewport?.height || innerHeight || 0);
      const offsetTop = Math.round(viewport?.offsetTop || 0);
      // Track max-seen innerHeight as stable baseline. On Android Chrome, window.innerHeight
      // shrinks along with visualViewport when the keyboard opens, so comparing the two gives
      // zero delta and keyboard is never detected. Comparing against the pre-keyboard peak fixes this.
      if (!this._stableAppVh || innerHeight > this._stableAppVh) {
        this._stableAppVh = innerHeight;
      }
      const stableH = this._stableAppVh;
      const keyboardOpen = Boolean(viewport && stableH && visualHeight < stableH - 100);
      const appHeight = Math.round(stableH || innerHeight || visualHeight || 0);
      if (appHeight > 0) {
        document.documentElement.style.setProperty("--app-vh", `${appHeight}px`);
      }
      if (visualHeight > 0) {
        document.documentElement.style.setProperty("--visual-vh", `${visualHeight}px`);
      }
      document.documentElement.style.setProperty("--viewport-offset-top", `${offsetTop}px`);
      const wasKeyboard = this._wasKeyboardOpen || false;
      this._wasKeyboardOpen = keyboardOpen;
      document.body.classList.toggle("keyboard-open", keyboardOpen);
      if (keyboardOpen) {
        // Prevent iOS from accumulating scroll offset on fixed layouts (older Safari fallback).
        if (typeof window.scrollTo === "function") {
          window.scrollTo(0, 0);
        }

      }
    },

    updateBodyClasses() {
      this.enforceStreamingOverlayPolicy();
      const body = document.body;
      const mobile = this.isMobileLayout();
      const standaloneMode = Boolean(
        (typeof window.matchMedia === "function" && window.matchMedia("(display-mode: standalone)").matches)
        || window.navigator.standalone
      );
      body.classList.toggle("sidebar-open", mobile && this.sidebarOpen);
      body.classList.toggle("sidebar-collapsed", !mobile && this.sidebarCollapsed);
      body.classList.toggle("standalone-mode", standaloneMode);
      body.classList.toggle("md-modal-open", this.mdOverlayOpen);
      body.classList.toggle("actions-modal-open", this.actionsOverlayOpen);
      body.classList.toggle("panel-modal-open", this.panelOverlayOpen);
      body.classList.toggle(
        "family-modal-open",
        this.familyProfileModalOpen ||
          this.agentGraphModalOpen ||
          this.imageToolStyleModalOpen ||
          this.imageToolPromptModalOpen ||
          this.videoToolOpen ||
          this.webPushModalOpen ||
          this.projectPickerOpen ||
          this.projectBranchModalOpen ||
          this.projectTargetModalOpen ||
          this.projectTopicTypeModalOpen ||
          this.libraryIntakeOpen ||
          this.waypointMemberEditorOpen ||
          this.waypointTaskModalOpen ||
          this.waypointEventModalOpen ||
          this.waypointShoppingModalOpen ||
          this.waypointContactModalOpen ||
          this.emailSettingsModalOpen ||
          this.botSettingsModalOpen
      );
    },

    toggleSidebar() {
      if (this.isMobileLayout()) {
        this.sidebarOpen = !this.sidebarOpen;
      } else {
        this.sidebarCollapsed = !this.sidebarCollapsed;
      }
      this.updateBodyClasses();
    },

    closeSidebar() {
      this.sidebarOpen = false;
      this.updateBodyClasses();
    },

    showWaypointRetiredNotice() {
      window.alert("Waypoint has been retired from Oathweaver.");
    },

    goToLandingHome() {
      this.chatMenuOpen = false;
      this.actionsOverlayOpen = false;
      this.panelOverlayOpen = false;
      if (this.isMobileLayout()) {
        this.closeSidebar();
      } else {
        this.sidebarCollapsed = true;
      }
      this.setActiveApp("home");
      this.updateBodyClasses();
    },

    setActiveApp(appName) {
      const key = String(appName || "").trim().toLowerCase();
      this.activeApp = key === "home" ? "home" : "chat";
      this.waypointBuilderOpen = false;
      this.waypointChatExpanded = false;
      this.closeWaypointEntryModals();
      this.updateBodyClasses();
      this.$nextTick(() => {
        if (this.activeApp === "chat") {
          this.resizeComposer();
          this.scrollMessages();
        }
      });
    },

    async openWaypointApp(options = {}) {
      this.setActiveApp("chat");
      this.showWaypointRetiredNotice();
    },

    async openWaypointMonthFromHome() {
      this.showWaypointRetiredNotice();
    },

    async openWaypointDayFromHome() {
      this.showWaypointRetiredNotice();
    },

    focusWaypointCaptureField(kind) {
      this.$nextTick(() => {
        const target =
          kind === "event"
            ? this.$refs.waypointEventTitleInput
            : kind === "shopping"
              ? this.$refs.waypointShoppingTitleInput
              : kind === "contact"
                ? this.$refs.waypointContactNameInput
                : this.$refs.waypointTaskTitleInput;
        if (target && typeof target.focus === "function") {
          target.focus();
        }
      });
    },

    openWaypointCapturePanel(kind, dateKey = "") {
      this.showWaypointRetiredNotice();
    },

    async openWaypointAddEventFromHome() {
      this.showWaypointRetiredNotice();
    },

    async openWaypointAddTaskFromHome() {
      this.showWaypointRetiredNotice();
    },

    async openWaypointAddShoppingFromHome() {
      this.showWaypointRetiredNotice();
    },

    async openLastConversationFromHome() {
      const id = String(this.homeLastConversation?.id || "").trim();
      if (!id) {
        await this.createConversation();
        return;
      }
      await this.openConversation(id);
    },

    async openHomeChat() {
      const id = String(this.homeLastConversation?.id || "").trim();
      if (id) {
        await this.openConversation(id);
        return;
      }
      if (Array.isArray(this.conversations) && this.conversations.length) {
        await this.openConversation(this.conversations[0].id);
        return;
      }
      await this.createConversation();
    },

    closeWaypointApp() {
      this.setActiveApp("chat");
    },

    closeWaypointEntryModals() {
      this.waypointTaskModalOpen = false;
      this.waypointEventModalOpen = false;
      this.waypointShoppingModalOpen = false;
      this.waypointContactModalOpen = false;
      this.updateBodyClasses();
    },

    openWaypointTaskModal(options = {}) {
      const dueDate = isIsoDate(String(options?.dueDate || "").trim()) ? String(options.dueDate).trim() : "";
      const listName = String(options?.listName || "general").trim() || "general";
      const memberIds = this.normalizeWaypointMemberIds(options?.memberIds || []);
      this.closeWaypointEntryModals();
      this.waypointTaskEditId = "";
      this.waypointTaskForm.title = "";
      this.waypointTaskForm.priority = "medium";
      this.waypointTaskForm.list_name = listName;
      this.waypointTaskForm.due_date = dueDate;
      this.waypointTaskForm.member_ids = memberIds;
      this.waypointTaskForm.location = "";
      this.waypointTaskForm.recurrence_enabled = false;
      this.waypointTaskForm.recurrence_type = "weekly_day";
      this.waypointTaskForm.recurrence_interval = 1;
      this.waypointTaskForm.recurrence_weekday = 0;
      this.waypointTaskForm.recurrence_day = 1;
      this.waypointTaskForm.recurrence_nth = 1;
      this.waypointTaskForm.recurrence_until = "";
      this.waypointTaskModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("task");
    },

    openWaypointTaskEditModal(task) {
      const row = task && typeof task === "object" ? task : {};
      const taskId = String(row.id || "").trim();
      if (!taskId) {
        return;
      }
      this.closeWaypointEntryModals();
      this.waypointTaskEditId = taskId;
      this.waypointTaskForm.title = String(row.title || "").trim();
      this.waypointTaskForm.priority = String(row.priority || "medium").trim() || "medium";
      this.waypointTaskForm.list_name = String(row.list_name || "general").trim() || "general";
      this.waypointTaskForm.due_date = String(row.due_date || "").trim();
      this.waypointTaskForm.member_ids = this.normalizeWaypointMemberIds(row.member_ids || []);
      this.waypointTaskForm.location = String(row.location || "").trim();
      this.waypointTaskForm.recurrence_enabled = Boolean(row.recurrence_enabled);
      this.waypointTaskForm.recurrence_type = String(row.recurrence_type || "weekly_day").trim() || "weekly_day";
      this.waypointTaskForm.recurrence_interval = Number(row.recurrence_interval) || 1;
      this.waypointTaskForm.recurrence_weekday = Number(row.recurrence_weekday) || 0;
      this.waypointTaskForm.recurrence_day = Number(row.recurrence_day) || 1;
      this.waypointTaskForm.recurrence_nth = Number(row.recurrence_nth) || 1;
      this.waypointTaskForm.recurrence_until = String(row.recurrence_until || "").trim();
      this.waypointTaskModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("task");
    },

    closeWaypointTaskModal() {
      this.waypointTaskModalOpen = false;
      this.waypointTaskEditId = "";
      this.updateBodyClasses();
    },

    openWaypointReminderTaskModal() {
      this.openWaypointTaskModal({
        listName: "reminders",
        dueDate: isIsoDate(String(this.waypointSelectedDateKey || "").trim()) ? String(this.waypointSelectedDateKey).trim() : "",
      });
    },

    openWaypointEventModal(dateKey = "") {
      const selected = isIsoDate(String(dateKey || "").trim())
        ? String(dateKey).trim()
        : isIsoDate(String(this.waypointSelectedDateKey || "").trim())
          ? String(this.waypointSelectedDateKey).trim()
          : toDateKey(startOfLocalDay(new Date()));
      const hostOptions = Array.isArray(this.waypointHostContactLocationOptions) ? this.waypointHostContactLocationOptions : [];
      const defaultHostContactId = hostOptions.length === 1 ? String(hostOptions[0]?.value || "").trim() : "";
      const selectedWeekday = this.waypointDefaultRecurrenceWeekdayForDate(selected);
      const selectedNth = this.waypointDefaultRecurrenceNthForDate(selected);
      const parsedSelected = parseDateKey(selected) || startOfLocalDay(new Date());
      this.closeWaypointEntryModals();
      this.waypointEventEditId = "";
      this.waypointEventForm.title = "";
      this.waypointEventForm.date = selected;
      this.waypointEventForm.start_time = "";
      this.waypointEventForm.end_time = "";
      this.waypointEventForm.reminder_time = "";
      this.waypointEventForm.location_contact_id = defaultHostContactId;
      this.waypointEventForm.location = "";
      this.waypointEventForm.member_ids = [];
      this.waypointEventForm.recurrence_enabled = false;
      this.waypointEventForm.recurrence_type = "weekly_day";
      this.waypointEventForm.recurrence_interval = 1;
      this.waypointEventForm.recurrence_weekday = selectedWeekday;
      this.waypointEventForm.recurrence_day = parsedSelected.getDate();
      this.waypointEventForm.recurrence_nth = selectedNth;
      this.waypointEventForm.recurrence_until = "";
      if (defaultHostContactId) {
        this.onWaypointEventLocationContactChanged();
      }
      this.waypointEventModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("event");
    },

    openWaypointEventEditModal(eventRow) {
      const row = eventRow && typeof eventRow === "object" ? eventRow : {};
      const eventId = String(row.source_id || row.id || "").trim();
      if (!eventId) {
        return;
      }
      this.closeWaypointEntryModals();
      this.waypointEventEditId = eventId;
      const hostIds = new Set((this.waypointHostContactLocationOptions || []).map((opt) => String(opt?.value || "").trim()));
      const contactId = String(row.location_contact_id || "").trim();
      this.waypointEventForm.title = String(row.title || "").trim();
      this.waypointEventForm.date = String(row.date || "").trim();
      this.waypointEventForm.start_time = String(row.start_time || "").trim();
      this.waypointEventForm.end_time = String(row.end_time || "").trim();
      this.waypointEventForm.location_contact_id = hostIds.has(contactId) ? contactId : "";
      this.waypointEventForm.location = String(row.location || "").trim();
      this.waypointEventForm.reminder_time = this.extractReminderTimeFromNotes(row.notes || "");
      this.waypointEventForm.member_ids = this.normalizeWaypointMemberIds(row.member_ids || []);
      const recurrence = this.normalizeWaypointEventRecurrence(row);
      this.waypointEventForm.recurrence_enabled = Boolean(recurrence.recurrence_enabled);
      this.waypointEventForm.recurrence_type = String(recurrence.recurrence_type || "weekly_day");
      this.waypointEventForm.recurrence_interval = Number(recurrence.recurrence_interval || 1);
      this.waypointEventForm.recurrence_weekday = Number(recurrence.recurrence_weekday || 0);
      this.waypointEventForm.recurrence_day = Number(recurrence.recurrence_day || 1);
      this.waypointEventForm.recurrence_nth = Number(recurrence.recurrence_nth || 1);
      this.waypointEventForm.recurrence_until = String(recurrence.recurrence_until || "");
      if (this.waypointEventForm.location_contact_id) {
        this.onWaypointEventLocationContactChanged();
      }
      this.waypointEventModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("event");
    },

    closeWaypointEventModal() {
      this.waypointEventModalOpen = false;
      this.waypointEventEditId = "";
      this.updateBodyClasses();
    },

    syncWaypointEventRecurrenceFromDate() {
      const dateKey = String(this.waypointEventForm.date || "").trim();
      if (!isIsoDate(dateKey)) {
        return;
      }
      this.waypointEventForm.recurrence_weekday = this.waypointDefaultRecurrenceWeekdayForDate(dateKey);
      this.waypointEventForm.recurrence_day = (parseDateKey(dateKey) || startOfLocalDay(new Date())).getDate();
      this.waypointEventForm.recurrence_nth = this.waypointDefaultRecurrenceNthForDate(dateKey);
    },

    openWaypointShoppingModal(defaultCategory = "food") {
      const category = String(defaultCategory || "food").trim().toLowerCase();
      this.closeWaypointEntryModals();
      this.waypointShoppingEditId = "";
      this.waypointShoppingForm.title = "";
      this.waypointShoppingForm.category = category === "general" ? "general" : "food";
      this.waypointShoppingModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("shopping");
    },

    openWaypointShoppingEditModal(item) {
      const row = item && typeof item === "object" ? item : {};
      const itemId = String(row.id || "").trim();
      if (!itemId) {
        return;
      }
      this.closeWaypointEntryModals();
      this.waypointShoppingEditId = itemId;
      this.waypointShoppingForm.title = String(row.title || "").trim();
      this.waypointShoppingForm.category = String(row.category || "food").trim().toLowerCase() === "general" ? "general" : "food";
      this.waypointShoppingModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("shopping");
    },

    closeWaypointShoppingModal() {
      this.waypointShoppingModalOpen = false;
      this.waypointShoppingEditId = "";
      this.updateBodyClasses();
    },

    openWaypointContactModal() {
      this.closeWaypointEntryModals();
      this.waypointContactEditId = "";
      this.waypointContactDeleteConfirm = "";
      this.waypointContactDetailsOpen = true;
      this.waypointContactForm = blankWaypointContactFormDefaults();
      this.waypointContactModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("contact");
    },

    openWaypointContactEditModal(person) {
      const row = person && typeof person === "object" ? person : {};
      const contactId = String(row.id || "").trim();
      if (!contactId) {
        return;
      }
      this.closeWaypointEntryModals();
      this.waypointContactEditId = contactId;
      this.waypointContactDeleteConfirm = "";
      this.waypointContactForm = Object.assign(blankWaypointContactFormDefaults(), {
        name: String(row.name || "").trim(),
        kind: String(row.kind || "person").trim().toLowerCase() || "person",
        relationship: String(row.relationship || "friend").trim().toLowerCase() || "friend",
        location_name: String(row.location_name || "").trim(),
        location_address: String(row.location_address || "").trim(),
        notes: String(row.notes || "").trim(),
        nickname: String(row.nickname || "").trim(),
        birthday: String(row.birthday || "").trim(),
        age: String(row.age || "").trim(),
        age_is_estimate: Boolean(row.age_is_estimate),
        gender: String(row.gender || "").trim(),
        school_or_work: String(row.school_or_work || "").trim(),
        likes: String(row.likes || "").trim(),
        dislikes: String(row.dislikes || "").trim(),
        important_dates: String(row.important_dates || "").trim(),
        medical_notes: String(row.medical_notes || "").trim(),
        email: String(row.email || "").trim(),
        phone: String(row.phone || "").trim(),
      });
      if (String(this.waypointContactForm.birthday || "").trim()) {
        this.waypointContactForm.age = "";
        this.waypointContactForm.age_is_estimate = false;
      }
      this.waypointContactDetailsOpen = true;
      this.waypointContactModalOpen = true;
      this.updateBodyClasses();
      this.focusWaypointCaptureField("contact");
    },

    closeWaypointContactModal() {
      this.waypointContactModalOpen = false;
      this.waypointContactEditId = "";
      this.waypointContactDeleteConfirm = "";
      this.waypointContactDetailsOpen = false;
      this.updateBodyClasses();
    },

    toggleWaypointChatTray() {
      if (!this.isMobileLayout()) {
        return;
      }
      this.waypointChatExpanded = !this.waypointChatExpanded;
      if (!this.waypointChatExpanded) {
        this.waypointBuilderOpen = false;
      }
      this.$nextTick(() => {
        if (!this.waypointChatExpanded) {
          return;
        }
        this.resizeWaypointComposer();
        this.scrollWaypointMessages();
        const node = this.$refs.waypointInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    setComposerMode(mode) {
      const next = mode === "forage" || mode === "make" || mode === "plan" || mode === "talk" ? mode : "talk";
      if (next !== "make" && this.pendingExtendsRequestId) {
        this.clearPendingMakeOutputExtension();
      }
      this.inputMode = next;
      try {
        localStorage.setItem("oathweaver_input_mode", this.inputMode);
      } catch (_err) {}
    },

    resetComposerMode() {
      this.setComposerMode("talk");
    },

    normalizeThemeName(raw) {
      const value = String(raw || "").trim();
      if (this.themeOptions.includes(value)) {
        return value;
      }
      return "Night";
    },

    async applyFontConfig(preferredFontId = "", persistChoice = false) {
      const defaultStack = "\"Segoe UI\", \"Trebuchet MS\", sans-serif";
      this.fontConfigError = "";
      document.documentElement.style.setProperty("--font-main", defaultStack);
      const styleId = "oathweaver-dynamic-fonts";
      try {
        let payload = null;
        let lastStatus = 0;
        for (const url of [FONT_CONFIG_API_URL, FONT_CONFIG_URL]) {
          try {
            const response = await fetch(url, { cache: "no-store" });
            if (!response.ok) {
              lastStatus = response.status;
              continue;
            }
            payload = await response.json();
            if (payload && typeof payload === "object") {
              break;
            }
          } catch (_err) {}
        }
        if (!payload || typeof payload !== "object") {
          this.fontOptions = [];
          this.activeFontId = "";
          this.fontConfigError = `Font config unavailable (${lastStatus || "load failed"}).`;
          return;
        }
        const rows = Array.isArray(payload?.fonts) ? payload.fonts : [];
        const fonts = [];
        for (const row of rows) {
          if (!row || typeof row !== "object") {
            continue;
          }
          const id = String(row.id || "").trim().toLowerCase();
          const family = String(row.family || "").trim();
          if (!id || !family || /[{};]/.test(family)) {
            continue;
          }
          let file = String(row.file || "").trim().replace(/\\/g, "/");
          if (file.startsWith("/")) {
            file = file.slice(1);
          }
          if (file.includes("..")) {
            file = "";
          }
          let format = String(row.format || "").trim().toLowerCase();
          if (!format && file.toLowerCase().endsWith(".otf")) {
            format = "opentype";
          }
          if (!format) {
            format = "truetype";
          }
          fonts.push({
            id,
            family,
            file,
            format,
            weight: String(row.weight || "400").trim() || "400",
            style: String(row.style || "normal").trim().toLowerCase() || "normal",
            fallback: String(row.fallback || "").trim(),
          });
        }
        this.fontOptions = fonts.map((row) => ({ id: row.id, family: row.family }));
        if (!fonts.length) {
          this.activeFontId = "";
          return;
        }

        let faceCss = "";
        for (const font of fonts) {
          if (!font.file) {
            continue;
          }
          const srcUrl = `/static/fonts/${encodeURI(font.file)}`;
          const safeFamily = font.family.replace(/"/g, '\\"');
          const formatHint = String(font.format || "").trim().toLowerCase();
          const srcParts = formatHint
            ? [`url("${srcUrl}") format("${formatHint}")`, `url("${srcUrl}")`]
            : [`url("${srcUrl}")`];
          faceCss += `@font-face{font-family:"${safeFamily}";src:${srcParts.join(",")};font-weight:${font.weight};font-style:${font.style};font-display:swap;}\n`;
        }
        let styleNode = document.getElementById(styleId);
        if (!styleNode) {
          styleNode = document.createElement("style");
          styleNode.id = styleId;
          document.head.appendChild(styleNode);
        }
        styleNode.textContent = faceCss;

        let savedId = "";
        let savedFamily = "";
        try {
          savedId = String(localStorage.getItem("oathweaver_font_id") || "").trim().toLowerCase();
          savedFamily = String(localStorage.getItem("oathweaver_font_family") || "").trim().toLowerCase();
        } catch (_err) {}

        const forcedId = String(preferredFontId || "").trim().toLowerCase();
        const configActiveId = String(payload?.active || "").trim().toLowerCase();
        let active =
          fonts.find((row) => row.id === forcedId) ||
          fonts.find((row) => row.id === savedId) ||
          fonts.find((row) => row.family.toLowerCase() === savedFamily) ||
          fonts.find((row) => row.id === configActiveId);
        if (!active) {
          const activeFamily = String(payload?.active_family || "").trim().toLowerCase();
          if (activeFamily) {
            active = fonts.find((row) => row.family.toLowerCase() === activeFamily);
          }
        }
        if (!active) {
          active = fonts[0];
        }

        const fallback = String(active?.fallback || payload?.fallback || defaultStack).trim() || defaultStack;
        const safeFamily = String(active.family || "").replace(/"/g, '\\"');
        document.documentElement.style.setProperty("--font-main", `"${safeFamily}", ${fallback}`);
        this.activeFontId = String(active.id || "").trim().toLowerCase();

        try {
          localStorage.setItem("oathweaver_font_id", this.activeFontId);
          localStorage.setItem("oathweaver_font_family", String(active.family || "").trim());
        } catch (_err) {}
      } catch (err) {
        console.warn("Font config load failed:", err);
        this.fontConfigError = "Could not load font settings.";
      }
    },

    async setUiFont(fontId) {
      const next = String(fontId || "").trim().toLowerCase();
      if (!next) {
        return;
      }
      await this.applyFontConfig(next, true);
    },

    applyTheme(rawTheme, persist = true) {
      const next = this.normalizeThemeName(rawTheme);
      this.theme = next;
      document.body.classList.toggle('dark', next === 'Night');
      document.body.classList.toggle('day', next === 'Day');
      if (!persist) {
        return;
      }
      try {
        localStorage.setItem("oathweaver_theme", next);
      } catch (_err) {}
    },

    cycleTheme() {
      this.chatMenuOpen = false;
      const index = this.themeOptions.indexOf(this.theme);
      const next = this.themeOptions[(index + 1) % this.themeOptions.length];
      this.applyTheme(next, true);
    },

    setActiveProject(project) {
      const nextProject = normalizeProjectSlug(project);
      const previous = String(this.activeProject || "").trim();
      this.activeProject = nextProject;
      if (previous !== nextProject && this.pendingExtendsRequestId) {
        this.clearPendingMakeOutputExtension();
      }
      try {
        localStorage.setItem("oathweaver_active_project", this.activeProject);
      } catch (_err) {}
      this.refreshProjectPipeline().catch(() => {});
    },

    async refreshSidebarProjectLane() {
      if (this.sidebarProjectsLoading) {
        return;
      }
      this.sidebarProjectsLoading = true;
      this.sidebarProjectsError = "";
      try {
        const [projectsPayload, topicsPayload] = await Promise.all([
          this.apiGet("/api/panel/projects?limit=200"),
          this.apiGet("/api/topics"),
        ]);
        this.sidebarProjectRows = Array.isArray(projectsPayload?.projects) ? projectsPayload.projects : [];
        this.sidebarTopicRows = Array.isArray(topicsPayload?.topics) ? topicsPayload.topics : [];
        this.sidebarProjectsFetchedAt = Date.now();
      } catch (err) {
        this.sidebarProjectsError = String(err?.message || err);
        this.sidebarProjectRows = [];
        this.sidebarTopicRows = [];
      } finally {
        this.sidebarProjectsLoading = false;
      }
    },

    async ensureSidebarProjectLaneFresh(options = {}) {
      const force = Boolean(options?.force);
      const staleMs = Number(options?.staleMs || 45_000);
      if (this.sidebarProjectsLoading) {
        return;
      }
      const fetchedAt = Number(this.sidebarProjectsFetchedAt || 0);
      if (!force && fetchedAt > 0 && Date.now() - fetchedAt < staleMs) {
        return;
      }
      await this.refreshSidebarProjectLane();
    },

    preferredTopicIdForProject(projectSlug) {
      const slug = normalizeProjectSlug(projectSlug || "");
      if (!slug || slug === "general") {
        return "";
      }
      const rows = Array.isArray(this.conversations) ? this.conversations : [];
      for (const row of rows) {
        if (normalizeProjectSlug(row?.project || "") !== slug) {
          continue;
        }
        const topicId = String(row?.topic_id || "").trim();
        if (topicId && topicId !== "general") {
          return topicId;
        }
      }
      return "";
    },

    latestConversationForProject(projectSlug) {
      const slug = normalizeProjectSlug(projectSlug || "");
      if (!slug) {
        return null;
      }
      const rows = Array.isArray(this.conversations) ? this.conversations : [];
      for (const row of rows) {
        if (normalizeProjectSlug(row?.project || "") === slug) {
          return row;
        }
      }
      return null;
    },

    async openProjectWorkspace(projectSlug) {
      const slug = normalizeProjectSlug(projectSlug || "general");
      if (!slug || slug === "general") {
        return;
      }
      this.setActiveProject(slug);
      const existing = this.latestConversationForProject(slug);
      if (existing?.id) {
        await this.openConversation(existing.id, { activateApp: true });
        return;
      }
      const topicId = this.preferredTopicIdForProject(slug);
      await this.createConversation("project", {
        project: slug,
        topicId: topicId || undefined,
        activateApp: true,
      });
    },

    async openProjectDetailFromSidebar(projectSlug) {
      const slug = normalizeProjectSlug(projectSlug || "general");
      if (!slug || slug === "general") {
        return;
      }
      this.setActiveProject(slug);
      await this.openSystemPanel("project_detail");
    },

    async openProjectContentFromSidebar(projectSlug) {
      const slug = normalizeProjectSlug(projectSlug || "general");
      if (!slug || slug === "general") {
        return;
      }
      this.setActiveProject(slug);
      await this.openSystemPanel("content");
    },

    projectModeTitle(mode) {
      const key = String(mode || "").trim().toLowerCase();
      const row = PROJECT_PIPELINE_MODES.find((x) => x.value === key);
      return row ? row.label : "Discovery";
    },

    topicTypeLabel(type) {
      const key = String(type || "").trim().toLowerCase();
      const row = TOPIC_TYPES.find((x) => x.value === key);
      return row ? row.label : "General";
    },

    conversationTopicType(conversation) {
      const topicId = String(conversation?.topic_id || "").trim();
      if (topicId && topicId !== "general") {
        const topic = (Array.isArray(this.sidebarTopicRowsEffective) ? this.sidebarTopicRowsEffective : []).find(
          (row) => String(row?.id || "").trim() === topicId
        );
        const type = String(topic?.type || "").trim().toLowerCase();
        if (type) {
          return type;
        }
      }
      return "general";
    },

    conversationProjectTagText(conversation) {
      const type = this.conversationTopicType(conversation);
      const row = TOPIC_TYPES.find((x) => x.value === type);
      return row ? row.label : "General Research";
    },

    projectTargetTitle(target) {
      const key = String(target || "").trim().toLowerCase();
      const row = MAKE_TARGETS.find((x) => x.value === key);
      return row ? row.label : "Auto";
    },

    async refreshProjectPipeline() {
      const project = normalizeProjectSlug(this.activeProject);
      if (!project) {
        return;
      }
      try {
        const payload = await this.apiGet(`/api/projects/${encodeURIComponent(project)}/mode`);
        this.projectPipeline = {
          project,
          mode: String(payload?.mode || "discovery").trim().toLowerCase() || "discovery",
          target: String(payload?.target || "auto").trim().toLowerCase() || "auto",
          topic_type: String(payload?.topic_type || "general").trim().toLowerCase() || "general",
          updated_at: String(payload?.updated_at || "").trim(),
        };
      } catch (_err) {
        this.projectPipeline = {
          project,
          mode: "discovery",
          target: "auto",
          topic_type: "general",
          updated_at: "",
        };
      }
    },

    async setProjectModeDirect(mode) {
      const project = normalizeProjectSlug(this.activeProject);
      const nextMode = String(mode || "").trim().toLowerCase();
      if (!project || !nextMode) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/projects/${encodeURIComponent(project)}/mode`, {
          mode: nextMode,
        });
        this.projectPipeline = {
          project,
          mode: String(payload?.mode || "discovery").trim().toLowerCase() || "discovery",
          target: String(payload?.target || "auto").trim().toLowerCase() || "auto",
          topic_type: String(payload?.topic_type || "general").trim().toLowerCase() || "general",
          updated_at: String(payload?.updated_at || "").trim(),
        };
        await this.refreshSystemPanel();
      } catch (err) {
        window.alert(`Project mode update failed: ${String(err.message || err)}`);
      }
    },

    async toggleProjectMode() {
      this.chatMenuOpen = false;
      const cycle = ["discovery", "make"];
      const current = String(this.projectPipeline?.mode || "discovery").toLowerCase();
      const idx = cycle.indexOf(current);
      const next = cycle[(idx + 1) % cycle.length];
      await this.setProjectModeDirect(next);
    },

    async setProjectBuildTarget() {
      this.openProjectBuildTargetModal();
    },

    openProjectTopicTypeModal() {
      this.chatMenuOpen = false;
      this.projectTopicTypeError = "";
      this.projectTopicTypeSubmitting = false;
      this.projectTopicTypeForm = {
        topic_type: String(this.projectPipeline?.topic_type || "general").trim().toLowerCase() || "general",
      };
      this.projectTopicTypeModalOpen = true;
      this.updateBodyClasses();
      this.$nextTick(() => {
        const node = this.$refs.projectTopicTypeSelect;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    closeProjectTopicTypeModal() {
      this.projectTopicTypeModalOpen = false;
      this.projectTopicTypeSubmitting = false;
      this.projectTopicTypeError = "";
      this.updateBodyClasses();
    },

    async submitProjectTopicTypeModal() {
      const topicType = String(this.projectTopicTypeForm?.topic_type || "general").trim().toLowerCase() || "general";
      const project = normalizeProjectSlug(this.activeProject);
      try {
        this.projectTopicTypeSubmitting = true;
        this.projectTopicTypeError = "";
        const payload = await this.apiPost(`/api/projects/${encodeURIComponent(project)}/mode`, {
          topic_type: topicType,
        });
        this.projectPipeline = {
          project,
          mode: String(payload?.mode || "discovery").trim().toLowerCase() || "discovery",
          target: String(payload?.target || "auto").trim().toLowerCase() || "auto",
          topic_type: String(payload?.topic_type || topicType).trim().toLowerCase() || "general",
          updated_at: String(payload?.updated_at || "").trim(),
        };
        await this.refreshSystemPanel();
        this.closeProjectTopicTypeModal();
      } catch (err) {
        this.projectTopicTypeError = String(err.message || err);
      } finally {
        this.projectTopicTypeSubmitting = false;
      }
    },

    openProjectBuildTargetModal() {
      this.chatMenuOpen = false;
      this.projectTargetError = "";
      this.projectTargetSubmitting = false;
      this.projectTargetForm = {
        target: String(this.projectPipeline?.target || "auto").trim().toLowerCase() || "auto",
      };
      this.projectTargetModalOpen = true;
      this.updateBodyClasses();
      this.$nextTick(() => {
        const node = this.$refs.projectTargetSelect;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    closeProjectBuildTargetModal() {
      this.projectTargetModalOpen = false;
      this.projectTargetSubmitting = false;
      this.projectTargetError = "";
      this.updateBodyClasses();
    },

    async submitProjectBuildTargetModal() {
      const target = String(this.projectTargetForm?.target || "")
        .trim()
        .toLowerCase();
      if (!MAKE_TARGETS.some((x) => x.value === target)) {
        this.projectTargetError = "Select a valid make target.";
        return;
      }
      const project = normalizeProjectSlug(this.activeProject);
      try {
        this.projectTargetSubmitting = true;
        this.projectTargetError = "";
        const payload = await this.apiPost(`/api/projects/${encodeURIComponent(project)}/mode`, {
          target,
        });
        this.projectPipeline = {
          project,
          mode: String(payload?.mode || "discovery").trim().toLowerCase() || "discovery",
          target: String(payload?.target || "auto").trim().toLowerCase() || "auto",
          topic_type: String(payload?.topic_type || "general").trim().toLowerCase() || "general",
          updated_at: String(payload?.updated_at || "").trim(),
        };
        await this.refreshSystemPanel();
        this.closeProjectBuildTargetModal();
      } catch (err) {
        this.projectTargetError = String(err.message || err);
      } finally {
        this.projectTargetSubmitting = false;
      }
    },

    async loadTopicPickerRows() {
      try {
        const payload = await this.apiGet("/api/topics");
        this.topicPickerRows = Array.isArray(payload.topics) ? payload.topics : [];
      } catch (_err) {
        this.topicPickerRows = [];
      }
    },

    openTopicPickerModal(mode = "set") {
      this.chatMenuOpen = false;
      this.topicPickerMode = mode === "create" ? "create" : "set";
      this.topicPickerSearch = "";
      this.topicPickerOpen = true;
      this.loadTopicPickerRows();
      this.updateBodyClasses();
    },

    closeTopicPickerModal() {
      this.topicPickerOpen = false;
      this.updateBodyClasses();
    },

    async confirmTopicSelection(topic) {
      if (!topic) return;
      if (String(topic.type || "").trim().toLowerCase() === "underground") {
        this.undergroundWarningPendingTopic = topic;
        this.undergroundWarningOpen = true;
        return;
      }
      if (this.topicPickerMode === "create") {
        await this.startProjectFromTopic(topic);
      } else {
        await this.setTopicActive(topic);
      }
      this.closeTopicPickerModal();
    },

    async confirmUndergroundAndProceed() {
      this.undergroundWarningOpen = false;
      const topic = this.undergroundWarningPendingTopic;
      this.undergroundWarningPendingTopic = null;
      if (!topic) return;
      if (this.topicPickerMode === "create") {
        await this.startProjectFromTopic(topic);
      } else {
        await this.setTopicActive(topic);
      }
      this.closeTopicPickerModal();
    },

    cancelUndergroundWarning() {
      this.undergroundWarningOpen = false;
      this.undergroundWarningPendingTopic = null;
    },

    goToTopicsPanel() {
      this.closeTopicPickerModal();
      this.openSystemPanel("topics");
    },

    async setTopicActive(topic) {
      const slug = normalizeProjectSlug(topic.slug || topic.name || "general");
      const topicType = String(topic.type || "general").trim().toLowerCase() || "general";
      const topicId = normalizeTopicId(topic.id || "general");
      try {
        await this.setConversationTopic(topicId, slug);
        const project = normalizeProjectSlug(this.activeProject);
        const payload = await this.apiPost(`/api/projects/${encodeURIComponent(project)}/mode`, {
          topic_type: topicType,
        });
        this.projectPipeline = {
          project,
          mode: String(payload?.mode || "discovery").trim().toLowerCase() || "discovery",
          target: String(payload?.target || "auto").trim().toLowerCase() || "auto",
          topic_type: String(payload?.topic_type || topicType).trim().toLowerCase() || "general",
          updated_at: String(payload?.updated_at || "").trim(),
        };
        this.activeTopicId = topicId;
        await this.ensureSidebarProjectLaneFresh({ force: true });
      } catch (err) {
        window.alert(`Set topic failed: ${String(err.message || err)}`);
      }
    },


    async startProjectFromTopic(topic) {
      if (!topic) return;
      const slug = normalizeProjectSlug(topic.slug || topic.name || "general");
      const topicId = normalizeTopicId(topic.id || "general");
      await this.createConversation("project", { project: slug, topicId, activateApp: true });
    },

    beginProjectCreation() {
      this.openTopicPickerModal("create");
    },

    async createTopic() {
      if (!this.topicFormValid) return;
      try {
        await this.apiPost("/api/topics", {
          name: String(this.topicForm.name || "").trim(),
          type: String(this.topicForm.type || "").trim(),
          description: String(this.topicForm.description || "").trim(),
          seed_question: String(this.topicForm.seed_question || "").trim(),
          parent_id: String(this.topicForm.parent_id || "").trim(),
        });
        this.topicForm = { name: "", type: "", description: "", seed_question: "", parent_id: "" };
        await this.refreshSystemPanel();
        await this.ensureSidebarProjectLaneFresh({ force: true });
      } catch (err) {
        window.alert(`Create topic failed: ${String(err.message || err)}`);
      }
    },

    async deleteTopic(topicId) {
      if (!window.confirm("Delete this topic and all its sub-topics?")) return;
      try {
        await this.apiDelete(`/api/topics/${encodeURIComponent(topicId)}`);
        await this.refreshSystemPanel();
        await this.ensureSidebarProjectLaneFresh({ force: true });
      } catch (err) {
        window.alert(`Delete topic failed: ${String(err.message || err)}`);
      }
    },

    async openTopicDetail(topic) {
      if (!topic || !topic.id) return;
      this._activePanelTopicId = String(topic.id || "").trim();
      await this.openSystemPanel("topic_detail");
    },

    async switchToTopicProject(project) {
      if (!project) return;
      const slug = String(project || "general").trim().replace(/\s+/g, "_").toLowerCase() || "general";
      try {
        await this.setConversationProjectSlug(slug);
      } catch (err) {
        console.warn("switchToTopicProject failed:", err);
      }
    },

    openResetModal() {
      this.resetConfirmText = "";
      this.resetLog = [];
      this.resetRunning = false;
      this.resetModalOpen = true;
    },

    closeResetModal() {
      if (this.resetRunning) return;
      this.resetModalOpen = false;
    },

    async submitReset() {
      if (this.resetConfirmText !== "RESET" || this.resetRunning) return;
      this.resetRunning = true;
      this.resetLog = [];
      try {
        const result = await this.apiPost("/api/system/reset-environment", { confirm: "RESET" });
        this.resetLog = Array.isArray(result.log) ? result.log.filter(Boolean) : [];
        if (result.ok) {
          this.resetLog.push("", "Reset complete. Reload the page to start fresh.");
        } else {
          this.resetLog.push(`Error: ${result.error || "unknown"}`);
        }
      } catch (err) {
        this.resetLog = [`Reset failed: ${String(err.message || err)}`];
      } finally {
        this.resetRunning = false;
      }
    },

    userContent(content) {
      return stripTalkPrefix(content);
    },

    assistantDisplayRaw(msg) {
      const cleaned = stripTrailingAssistantRule(String(msg?.content || ""))
        .replace(/\n?\[FORAGE:\s*"[^"]*"\]/gi, "")
        .replace(/\n?\[ADD_TASK:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_EVENT:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_SHOPPING:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_ROUTINE:[^\]]*\]/gi, "")
        .trimEnd();
      const id = String(msg?.id || "").trim();
      if (!id) {
        return cleaned;
      }
      const typing = this.assistantTypingByMessage && this.assistantTypingByMessage[id];
      if (!typing || typeof typing.text !== "string") {
        return cleaned;
      }
      if (typing.text !== cleaned) {
        this.stopAssistantTypewriter(id);
        return cleaned;
      }
      const shown = Math.max(0, Math.min(Number(typing.shown || 0), typing.text.length));
      return typing.text.slice(0, shown);
    },

    isAssistantTypewriting(msg) {
      const id = String(msg?.id || "").trim();
      if (!id) {
        return false;
      }
      const typing = this.assistantTypingByMessage && this.assistantTypingByMessage[id];
      if (!typing || typeof typing.text !== "string") {
        return false;
      }
      return Number(typing.shown || 0) < typing.text.length;
    },

    stopAssistantTypewriter(messageId) {
      const id = String(messageId || "").trim();
      if (!id) {
        return;
      }
      if (this._assistantTypingTimers && this._assistantTypingTimers[id]) {
        window.clearTimeout(this._assistantTypingTimers[id]);
        delete this._assistantTypingTimers[id];
      }
      if (this.assistantTypingByMessage && this.assistantTypingByMessage[id]) {
        const next = Object.assign({}, this.assistantTypingByMessage);
        delete next[id];
        this.assistantTypingByMessage = next;
      }
    },

    stopAllAssistantTypewriters() {
      if (this._assistantTypingTimers) {
        for (const timer of Object.values(this._assistantTypingTimers)) {
          window.clearTimeout(timer);
        }
      }
      this._assistantTypingTimers = {};
      this.assistantTypingByMessage = {};
    },

    startAssistantTypewriterForMessage(msg) {
      const id = String(msg?.id || "").trim();
      if (!id) {
        return;
      }
      const full = String(msg?.content || "")
        .replace(/\n?\[FORAGE:\s*"[^"]*"\]/gi, "")
        .replace(/\n?\[ADD_TASK:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_EVENT:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_SHOPPING:[^\]]*\]/gi, "")
        .replace(/\n?\[ADD_ROUTINE:[^\]]*\]/gi, "")
        .trimEnd();
      if (!full) {
        this.stopAssistantTypewriter(id);
        return;
      }
      if (!this._assistantTypingTimers) {
        this._assistantTypingTimers = {};
      }
      this.stopAssistantTypewriter(id);
      this.assistantTypingByMessage = Object.assign({}, this.assistantTypingByMessage, {
        [id]: { text: full, shown: 0 },
      });
      const total = full.length;
      const step = total > 6000 ? 34 : total > 3200 ? 22 : total > 1800 ? 14 : total > 900 ? 9 : 5;
      const delayMs = total > 3200 ? 10 : 14;
      let lastScrollTs = 0;
      const tick = () => {
        const row = this.assistantTypingByMessage && this.assistantTypingByMessage[id];
        if (!row || row.text !== full) {
          this.stopAssistantTypewriter(id);
          return;
        }
        const current = Number(row.shown || 0);
        if (current >= total) {
          this.stopAssistantTypewriter(id);
          this.$nextTick(() => this.scrollMessages());
          return;
        }
        const nextShown = Math.min(total, current + step);
        this.assistantTypingByMessage = Object.assign({}, this.assistantTypingByMessage, {
          [id]: { text: full, shown: nextShown },
        });
        const now = Date.now();
        if (now - lastScrollTs > 90) {
          lastScrollTs = now;
          this.$nextTick(() => this.scrollMessages());
        }
        if (nextShown >= total) {
          this.stopAssistantTypewriter(id);
          this.$nextTick(() => this.scrollMessages());
          return;
        }
        this._assistantTypingTimers[id] = window.setTimeout(tick, delayMs);
      };
      this._assistantTypingTimers[id] = window.setTimeout(tick, delayMs);
    },

    findLatestAssistantMessageForRequest(messages, requestId) {
      const rows = Array.isArray(messages) ? messages : [];
      const rid = String(requestId || "").trim();
      for (let i = rows.length - 1; i >= 0; i -= 1) {
        const row = rows[i];
        if (String(row?.role || "").trim().toLowerCase() !== "assistant") {
          continue;
        }
        if (!rid || String(row?.request_id || "").trim() === rid) {
          return row;
        }
      }
      return null;
    },

    startAssistantTypewriterFromConversation(conversation, requestId = "") {
      const rows = Array.isArray(conversation?.messages) ? conversation.messages : [];
      const target = this.findLatestAssistantMessageForRequest(rows, requestId);
      if (!target) {
        return;
      }
      this.startAssistantTypewriterForMessage(target);
    },

    assistantContent(msg) {
      const raw = this.assistantDisplayRaw(msg);
      const mode = String(msg?.mode || "").trim().toLowerCase();
      const isTalkLike = mode === "talk" || (!mode && !Boolean(msg?.foraging));
      const researchHtml = !isTalkLike ? renderResearchMessageHtml(msg) : "";
      if (researchHtml) {
        return this.isAssistantTypewriting(msg)
          ? `${researchHtml}<span class="msg-type-cursor" aria-hidden="true"></span>`
          : researchHtml;
      }
      const cacheKey = `${isTalkLike ? "talk" : "std"}|${raw.length}|${raw.slice(0, 180)}|${raw.slice(-96)}`;
      if (msg && typeof msg === "object") {
        const cached = ASSISTANT_HTML_CACHE.get(msg);
        if (cached && cached.key === cacheKey && typeof cached.html === "string") {
          return cached.html;
        }
      }
      const text = isTalkLike ? normalizeTalkDisplayMarkdown(raw) : raw;
      const htmlBase = markdownToHtml(decorateAssistantMarkdown(text));
      const html = this.isAssistantTypewriting(msg)
        ? `${htmlBase}<span class="msg-type-cursor" aria-hidden="true"></span>`
        : htmlBase;
      if (msg && typeof msg === "object") {
        ASSISTANT_HTML_CACHE.set(msg, { key: cacheKey, html });
      }
      return html;
    },

    assistantSourceStack(msg) {
      const raw = String(msg?.content || "");
      const persistedStackSources = Array.isArray(msg?.meta?.web_stack?.web_sources) ? msg.meta.web_stack.web_sources : [];
      const metaSources = Array.isArray(msg?.meta?.web_sources) && msg.meta.web_sources.length
        ? msg.meta.web_sources
        : persistedStackSources;
      const metaSignature = metaSources
        .slice(0, 6)
        .map((row) => String(row?.source_domain || row?.domain || row?.source_url || row?.url || "").trim().toLowerCase())
        .join("|");
      const cacheKey = `${raw.length}|${raw.slice(0, 180)}|${raw.slice(-96)}|meta:${metaSignature}`;
      if (msg && typeof msg === "object") {
        const cached = ASSISTANT_SOURCE_STACK_CACHE.get(msg);
        if (cached && cached.key === cacheKey && cached.value) {
          return cached.value;
        }
      }
      const sources = collectSourceEntries(raw, metaSources);
      const visible = sources.slice(0, 4);
      const result = {
        visible,
        overflow: Math.max(0, sources.length - visible.length),
        total: sources.length,
      };
      if (msg && typeof msg === "object") {
        ASSISTANT_SOURCE_STACK_CACHE.set(msg, { key: cacheKey, value: result });
      }
      return result;
    },

    assistantSourceStackTitle(msg) {
      const stack = this.assistantSourceStack(msg);
      if (!stack.total) {
        return "";
      }
      return stack.visible.map((row) => row.domain).join(", ");
    },

    sourceBubbleStyle(source, index) {
      const domain = String(source?.domain || "").trim().toLowerCase();
      let hash = 0;
      for (let i = 0; i < domain.length; i += 1) {
        hash = ((hash << 5) - hash + domain.charCodeAt(i)) | 0;
      }
      const hue = ((hash % 360) + 360) % 360;
      return {
        zIndex: 20 - Math.max(0, Number(index || 0)),
        "--src-ring": `hsl(${hue}, 74%, 62%)`,
        "--src-bg": `hsl(${hue}, 45%, 15%)`,
        "--src-glow": `hsla(${hue}, 84%, 58%, 0.32)`,
      };
    },

    sourceBubbleAriaLabel(source) {
      const domain = String(source?.domain || "").trim();
      if (!domain) {
        return "Source site";
      }
      return `Open source: ${domain}`;
    },

    onSourceBubbleIconError(event) {
      const target = event?.target;
      if (!(target instanceof HTMLImageElement)) {
        return;
      }
      const triedFallback = target.getAttribute("data-fallback") === "1";
      if (!triedFallback) {
        const domain = String(target.getAttribute("data-domain") || "").trim();
        if (domain) {
          target.setAttribute("data-fallback", "1");
          target.src = `https://icons.duckduckgo.com/ip3/${encodeURIComponent(domain)}.ico`;
          return;
        }
      }
      target.style.display = "none";
    },

    messageImageAttachments(msg) {
      const rows = Array.isArray(msg?.attachments) ? msg.attachments : [];
      return rows
        .map((item) => ({
          id: String(item?.id || "").trim(),
          type: String(item?.type || "").trim().toLowerCase(),
          url: String(item?.url || "").trim(),
          name: String(item?.name || "").trim(),
          filename: String(item?.filename || item?.name || "").trim(),
          modelFamily: String(item?.model_family || "").trim().toLowerCase(),
        }))
        .filter((item) => item.type === "image" && item.url);
    },

    messageVideoAttachments(msg) {
      const rows = Array.isArray(msg?.attachments) ? msg.attachments : [];
      return rows
        .map((item) => ({
          id: String(item?.id || "").trim(),
          type: String(item?.type || "").trim().toLowerCase(),
          url: String(item?.url || "").trim(),
          name: String(item?.name || "").trim(),
        }))
        .filter((item) => item.type === "video" && item.url);
    },

    msgWebStack(msg) {
      const persisted = msg?.meta?.web_stack;
      if (persisted && typeof persisted === "object" && (persisted.mode || persisted.source_count || (persisted.web_sources || []).length)) {
        return persisted;
      }
      const rid = String(msg?.request_id || "").trim();
      if (!rid) return null;
      const ws = this.jobWebStack[rid];
      if (!ws || typeof ws !== "object") return null;
      if (!ws.mode && !ws.source_count) return null;
      return ws;
    },

    toggleSourceExpand(msg) {
      const key = String(msg?.id || msg?.ts || "");
      if (!key) return;
      this.sourceExpandedMsgs = { ...this.sourceExpandedMsgs, [key]: !this.sourceExpandedMsgs[key] };
    },

    isSourceExpanded(msg) {
      const key = String(msg?.id || msg?.ts || "");
      return !!this.sourceExpandedMsgs[key];
    },

    syncImagePrefsFromConversation(convo) {
      const row = convo && typeof convo === "object" ? convo : {};
      const selected = this.normalizeLoraSelection(row?.selected_loras || []);
      this.composerSelectedLoras = selected;
      this.composerImageStyle = selected.length ? "lora" : "realistic";
    },

    normalizeLoraSelection(raw) {
      const values = Array.isArray(raw) ? raw : [];
      const seen = new Set();
      const out = [];
      for (const item of values) {
        const text = String(item || "").trim();
        if (!text || seen.has(text)) {
          continue;
        }
        seen.add(text);
        out.push(text);
      }
      return out.slice(0, 32);
    },

    async loadLoraOptions({ force = false } = {}) {
      if (!force && this.composerLoraOptions.length) {
        return;
      }
      this.composerLoraLoading = true;
      this.composerLoraError = "";
      try {
        const payload = await this.apiGet("/api/loras");
        const rows = Array.isArray(payload?.loras) ? payload.loras : [];
        this.composerLoraOptions = rows
          .map((row) => {
            const name = String(row?.name || row?.id || "").trim();
            if (!name) return null;
            return {
              id: String(row?.id || name).trim(),
              name,
              label: String(row?.label || "").trim() || name,
            };
          })
          .filter(Boolean);
      } catch (err) {
        this.composerLoraOptions = [];
        this.composerLoraError = String(err.message || err);
      } finally {
        this.composerLoraLoading = false;
      }
    },

    async loadImageToolPresets({ force = false } = {}) {
      if (!force && this.imageToolPresetOptions.length) {
        return;
      }
      this.imageToolPresetLoading = true;
      this.imageToolPresetError = "";
      try {
        const payload = await this.apiGet("/api/presets");
        const rows = Array.isArray(payload?.presets) ? payload.presets : [];
        this.imageToolPresetOptions = rows
          .map((row) => {
            const presetId = String(row?.id || "").trim().toLowerCase();
            if (!presetId) {
              return null;
            }
            const defaults = row?.defaults && typeof row.defaults === "object" ? row.defaults : {};
            return {
              id: presetId,
              label: String(row?.label || presetId).trim() || presetId,
              kind: String(row?.kind || "lora").trim().toLowerCase() || "lora",
              model_family: String(row?.model_family || "").trim().toLowerCase(),
              available: Boolean(row?.available),
              resolved_lora_name: String(row?.resolved_lora_name || "").trim(),
              defaults,
              default_negative_prompt: String(row?.default_negative_prompt || "").trim(),
              install_hint: String(row?.install_hint || "").trim(),
            };
          })
          .filter(Boolean);
        if (payload && typeof payload === "object" && String(payload.error || "").trim()) {
          this.imageToolPresetError = String(payload.error || "").trim();
        }
      } catch (err) {
        this.imageToolPresetOptions = [];
        this.imageToolPresetError = String(err.message || err);
      } finally {
        this.imageToolPresetLoading = false;
      }
    },

    async persistImagePreferences() {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return;
      }
      const selected = this.normalizeLoraSelection(this.composerSelectedLoras);
      const imageStyle = selected.length ? "lora" : "realistic";
      this.composerSelectedLoras = selected;
      this.composerImageStyle = imageStyle;
      try {
        const payload = await this.apiPatch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
          image_style: imageStyle,
          selected_loras: selected,
        });
        if (payload?.conversation) {
          this.syncImagePrefsFromConversation(payload.conversation);
          if (String(this.activeConversationId || "").trim() === conversationId) {
            this.activeConversation = payload.conversation;
          }
        }
      } catch (err) {
        console.warn("Image style preference save failed:", err);
      }
    },

    async toggleComposerAddMenu() {
      this.composerAddMenuOpen = !this.composerAddMenuOpen;
    },

    async setImageStyle(style) {
      const key = String(style || "").trim().toLowerCase();
      if (key !== "realistic") {
        return;
      }
      this.composerImageStyle = "realistic";
      this.composerSelectedLoras = [];
      await this.persistImagePreferences();
    },

    isLoraSelected(name) {
      const key = String(name || "").trim();
      if (!key) {
        return false;
      }
      return this.composerSelectedLoras.includes(key);
    },

    async toggleLoraSelection(name, checked) {
      const key = String(name || "").trim();
      if (!key) {
        return;
      }
      const next = this.normalizeLoraSelection(this.composerSelectedLoras);
      const has = next.includes(key);
      if (checked && !has) {
        next.push(key);
      } else if (!checked && has) {
        const idx = next.indexOf(key);
        if (idx >= 0) {
          next.splice(idx, 1);
        }
      }
      this.composerSelectedLoras = this.normalizeLoraSelection(next);
      this.composerImageStyle = this.composerSelectedLoras.length ? "lora" : "realistic";
      await this.persistImagePreferences();
    },

    clampImageToolSteps(raw) {
      const n = Number(raw);
      if (!Number.isFinite(n)) {
        return 28;
      }
      return Math.max(4, Math.min(80, Math.round(n)));
    },

    clampImageToolDimension(raw, fallback = 512) {
      const n = Number(raw);
      const base = Number.isFinite(n) ? n : fallback;
      const clipped = Math.max(256, Math.min(2048, Math.round(base)));
      return Math.max(256, Math.round(clipped / 8) * 8);
    },

    imageToolAspectForDimensions(width, height) {
      const w = this.clampImageToolDimension(width, 512);
      const h = this.clampImageToolDimension(height, 512);
      if (w > h) {
        return "landscape";
      }
      if (h > w) {
        return "portrait";
      }
      return "square";
    },

    setImageToolAspect(aspect) {
      const key = String(aspect || "").trim().toLowerCase();
      if (key === "landscape" || key === "portrait" || key === "square") {
        this.imageToolAspect = key;
      }
    },

    openPostbagItem(item) {
      this.postbagItemData = item;
      this.postbagItemOpen = true;
    },

    closePostbagItem() {
      this.postbagItemOpen = false;
      this.postbagItemData = null;
    },

    async handlePostbagItemAction(action) {
      const item = this.postbagItemData;
      if (!item) return;
      this.closePostbagItem();
      await this.handlePendingAction(item.id, action);
    },

    openLightbox(url, name) {
      this.lightboxUrl = url;
      this.lightboxName = name || "image";
      this.lightboxOpen = true;
    },

    closeLightbox() {
      this.lightboxOpen = false;
      this.lightboxUrl = "";
      this.lightboxName = "";
    },

    downloadLightboxImage() {
      const a = document.createElement("a");
      a.href = this.lightboxUrl;
      a.download = this.lightboxName;
      a.click();
    },

    setImageToolSubject(subject) {
      const key = String(subject || "").trim().toLowerCase();
      const valid = ["character", "object", "scene"];
      if (!key || !valid.includes(key)) {
        this.imageToolSubject = "";
      } else {
        this.imageToolSubject = this.imageToolSubject === key ? "" : key;
      }
    },

    imageToolResolutionForSelection(style = null, aspect = "square") {
      const row = style && typeof style === "object" ? style : this.imageToolSelectedStyle;
      const baseWidth = this.clampImageToolDimension(row?.defaultWidth, 512);
      const baseHeight = this.clampImageToolDimension(row?.defaultHeight, 512);
      const key = String(aspect || "square").trim().toLowerCase();
      if (key === "landscape") {
        return { width: 704, height: 512 };
      }
      if (key === "portrait") {
        return { width: 512, height: 704 };
      }
      const side = this.clampImageToolDimension(Math.min(baseWidth, baseHeight), 512);
      return { width: side, height: side };
    },

    imageToolStyleStorageKey(style = null) {
      const row = style && typeof style === "object" ? style : this.imageToolSelectedStyle;
      const presetId = String(row?.stylePresetId || "").trim().toLowerCase();
      if (presetId) {
        return presetId;
      }
      const kind = String(row?.kind || "realistic").trim().toLowerCase();
      return kind === "lora" ? "lora" : "realistic";
    },

    imageToolDefaultStepsForStyle(style = null) {
      const row = style && typeof style === "object" ? style : this.imageToolSelectedStyle;
      const storageKey = this.imageToolStyleStorageKey(row);
      const savedRaw = this.imageToolStepDefaults && typeof this.imageToolStepDefaults === "object"
        ? this.imageToolStepDefaults[storageKey]
        : undefined;
      if (Number.isFinite(Number(savedRaw))) {
        return this.clampImageToolSteps(savedRaw);
      }
      const fallback = Number(row?.defaultSteps);
      if (Number.isFinite(fallback)) {
        return this.clampImageToolSteps(fallback);
      }
      const kind = String(row?.kind || "realistic").trim().toLowerCase();
      return this.clampImageToolSteps(kind === "lora" ? 30 : 28);
    },

    imageToolSetStepsFromDefaults(style = null) {
      this.imageToolSteps = this.imageToolDefaultStepsForStyle(style);
    },

    saveImageToolDefaultStepsForCurrentStyle() {
      const storageKey = this.imageToolStyleStorageKey(this.imageToolSelectedStyle);
      const steps = this.clampImageToolSteps(this.imageToolSteps);
      this.imageToolSteps = steps;
      const nextDefaults = this.imageToolStepDefaults && typeof this.imageToolStepDefaults === "object"
        ? { ...this.imageToolStepDefaults }
        : {};
      nextDefaults[storageKey] = steps;
      this.imageToolStepDefaults = nextDefaults;
      try {
        localStorage.setItem("oathweaver_image_tool_step_defaults", JSON.stringify(nextDefaults));
      } catch (_err) {}
      const styleLabel = String(this.imageToolSelectedStyle?.label || "Selected Style").trim();
      this.imageToolDefaultSaveNote = `Saved default steps for ${styleLabel}.`;
      if (this._imageToolDefaultSaveTimer) {
        window.clearTimeout(this._imageToolDefaultSaveTimer);
      }
      this._imageToolDefaultSaveTimer = window.setTimeout(() => {
        this.imageToolDefaultSaveNote = "";
        this._imageToolDefaultSaveTimer = null;
      }, 2200);
    },

    loadImageToolStepDefaults() {
      if (this.imageToolStepDefaultsLoaded) {
        return;
      }
      let stepDefaults = {};
      try {
        const raw = localStorage.getItem("oathweaver_image_tool_step_defaults");
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            for (const [key, value] of Object.entries(parsed)) {
              const cleanKey = String(key || "").trim().toLowerCase();
              if (!cleanKey) {
                continue;
              }
              const n = Number(value);
              if (!Number.isFinite(n)) {
                continue;
              }
              stepDefaults[cleanKey] = this.clampImageToolSteps(n);
            }
          }
        }
      } catch (_err) {
        stepDefaults = {};
      }
      // One-time migration from the old per-kind keys.
      try {
        const oldReal = Number(localStorage.getItem("oathweaver_image_tool_default_steps_realistic"));
        const oldLora = Number(localStorage.getItem("oathweaver_image_tool_default_steps_lora"));
        if (Number.isFinite(oldReal) && stepDefaults.realistic === undefined) {
          stepDefaults.realistic = this.clampImageToolSteps(oldReal);
        }
        if (Number.isFinite(oldLora) && stepDefaults.lora === undefined) {
          stepDefaults.lora = this.clampImageToolSteps(oldLora);
        }
      } catch (_err) {}
      this.imageToolStepDefaults = stepDefaults;
      this.imageToolStepDefaultsLoaded = true;
      this.imageToolSetStepsFromDefaults(this.imageToolSelectedStyle);
    },

    async openImageToolStyleModal() {
      this.chatMenuOpen = false;
      this.composerAddMenuOpen = false;
      this.imageToolError = "";
      this.imageToolLastPromptFinal = "";
      this.imageToolDefaultSaveNote = "";
      this.imageToolAspect = "square";
      this.loadImageToolStepDefaults();
      this.imageToolStyleModalOpen = true;
      this.imageToolPromptModalOpen = false;
      this.updateBodyClasses();
      await this.loadImageToolPresets({ force: true });
    },

    closeImageToolStyleModal() {
      this.imageToolStyleModalOpen = false;
      this.updateBodyClasses();
    },

    closeImageToolPromptModal() {
      this.imageToolPromptModalOpen = false;
      this.imageToolSlashMenuOpen = false;
      this.imageToolBusy = false;
      this.imageToolDefaultSaveNote = "";
      this.updateBodyClasses();
    },

    onImageToolPromptKey(e) {
      if (this.imageToolSlashMenuOpen) {
        if (e.key === "Escape" || e.key === "Tab" || e.key === "Enter") {
          this.imageToolSlashMenuOpen = false;
          if (e.key === "Escape") e.preventDefault();
        }
        return;
      }
      if (e.key === "/" && this.imageToolRefSlots.length) {
        this.$nextTick(() => {
          const ta = this.$refs.imageToolPromptInput;
          this.imageToolSlashInsertStart = ta ? Math.max(0, (ta.selectionStart || 1) - 1) : 0;
          this.imageToolSlashMenuOpen = true;
        });
      }
    },

    insertImageRefSlot(slot) {
      const ta = this.$refs.imageToolPromptInput;
      if (!ta) {
        this.imageToolPrompt = (this.imageToolPrompt || "") + slot.token;
        this.imageToolSlashMenuOpen = false;
        return;
      }
      const val = this.imageToolPrompt || "";
      const cursorEnd = ta.selectionStart ?? val.length;
      const insertAt = this.imageToolSlashMenuOpen ? this.imageToolSlashInsertStart : cursorEnd;
      const replaceEnd = this.imageToolSlashMenuOpen ? cursorEnd : cursorEnd;
      this.imageToolPrompt = val.slice(0, insertAt) + slot.token + val.slice(replaceEnd);
      this.imageToolSlashMenuOpen = false;
      this.$nextTick(() => {
        const newPos = insertAt + slot.token.length;
        ta.setSelectionRange(newPos, newPos);
        ta.focus();
      });
    },

    selectImageToolStyle(style) {
      const row = style && typeof style === "object"
        ? style
        : {
          kind: "realistic",
          label: "Realistic (SD3.5)",
          modelFamily: "",
          familyTag: "",
          loras: [],
          stylePresetId: "",
          defaultSteps: 28,
          defaultRefinePrompt: true,
          defaultNegativePrompt: "",
          defaultWidth: 768,
          defaultHeight: 768,
        };
      if (row.disabled) {
        this.imageToolError = String(row.installHint || "This preset is not available yet.").trim();
        return;
      }
      const kind = String(row.kind || "realistic").trim().toLowerCase() === "lora" ? "lora" : "realistic";
      const modelFamilyRaw = String(row.modelFamily || "").trim().toLowerCase();
      const modelFamily = modelFamilyRaw === "sdxl" ? "xl" : modelFamilyRaw;
      const loras = this.normalizeLoraSelection(row.loras || []);
      this.imageToolSelectedStyle = {
        kind,
        label: String(row.label || (kind === "lora" ? "LoRA Style" : "Realistic (SD3.5)")).trim(),
        modelFamily,
        familyTag: String(row.familyTag || "").trim(),
        loras,
        stylePresetId: String(row.stylePresetId || "").trim().toLowerCase(),
        defaultSteps: Number(row.defaultSteps),
        defaultRefinePrompt: row.defaultRefinePrompt !== false,
        defaultNegativePrompt: String(row.defaultNegativePrompt || "").trim(),
        defaultWidth: Number(row.defaultWidth),
        defaultHeight: Number(row.defaultHeight),
      };
      this.imageToolSetStepsFromDefaults(this.imageToolSelectedStyle);
      this.imageToolAspect = "square";
      this.imageToolSubject = "";
      this.imageToolRefinePrompt = this.imageToolSelectedStyle.defaultRefinePrompt !== false;
      this.imageToolNegativePrompt = this.imageToolSelectedStyle.defaultNegativePrompt;
      this.imageToolStyleModalOpen = false;
      this.imageToolPromptModalOpen = true;
      this.imageToolError = "";
      this.imageToolLastPromptFinal = "";
      this.updateBodyClasses();
      this.$nextTick(() => {
        const node = this.$refs.imageToolPromptInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    async submitImageToolGenerate() {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId || this.imageToolBusy) {
        return;
      }
      const prompt = String(this.imageToolPrompt || "").trim();
      if (!prompt) {
        this.imageToolError = "Prompt is required.";
        return;
      }
      // Generate request_id now, before the call, so sessionStorage can persist it
      let imageRequestId = "";
      try {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          imageRequestId = String(window.crypto.randomUUID());
        }
      } catch (_e) {}
      if (!imageRequestId) {
        imageRequestId = `imgtool_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      }
      // Close modal immediately and show thinking bubble in chat
      this.imageToolPromptModalOpen = false;
      this.imageToolStyleModalOpen = false;
      this.imageToolBusy = true;
      this.imageToolError = "";
      this.imageToolLastPromptFinal = "";
      this.updateBodyClasses();
      this.setConversationSending(conversationId, {
        requestId: imageRequestId,
        startedAt: Date.now(),
        cancelRequested: false,
        foraging: false,
        renderJob: true,
      });
      this.$nextTick(() => this.scrollMessages());
      try {
        const loras = this.normalizeLoraSelection(this.imageToolSelectedStyle?.loras || []);
        const styleKind = String(this.imageToolSelectedStyle?.kind || "").trim().toLowerCase() === "lora"
          ? "lora"
          : "realistic";
        const modelFamilyRaw = String(this.imageToolSelectedStyle?.modelFamily || "").trim().toLowerCase();
        const modelFamily = modelFamilyRaw === "sdxl" ? "xl" : modelFamilyRaw;
        const stylePresetId = String(this.imageToolSelectedStyle?.stylePresetId || "").trim().toLowerCase();
        const steps = this.clampImageToolSteps(this.imageToolSteps);
        const dims = this.imageToolResolutionForSelection(this.imageToolSelectedStyle, this.imageToolAspect);
        this.imageToolSteps = steps;
        let payload = null;
        const imageRefs = this.imageToolUseComposerRefs
          ? (Array.isArray(this.composerImages) ? this.composerImages.filter((row) => !row?.isDoc) : [])
          : [];
        if (imageRefs.length) {
          const formData = new FormData();
          formData.append("prompt", prompt);
          formData.append("request_id", imageRequestId);
          formData.append("negative_prompt", String(this.imageToolNegativePrompt || "").trim());
          formData.append("refine_prompt", "true");
          formData.append("image_style", styleKind);
          formData.append("selected_loras", JSON.stringify(loras));
          if (modelFamily) {
            formData.append("model_family_override", modelFamily);
          }
          if (stylePresetId) {
            formData.append("style_preset_id", stylePresetId);
          }
          formData.append("steps", String(steps));
          formData.append("width", String(dims.width));
          formData.append("height", String(dims.height));
          if (this.imageToolSubject) {
            formData.append("scene_subject", this.imageToolSubject);
          }
          for (const row of imageRefs) {
            if (row?.file) {
              formData.append("images", row.file, row.name || "reference.png");
            }
          }
          payload = await this.apiPostForm(
            `/api/conversations/${encodeURIComponent(conversationId)}/image-tool/generate`,
            formData
          );
        } else {
          payload = await this.apiPost(
            `/api/conversations/${encodeURIComponent(conversationId)}/image-tool/generate`,
            {
              prompt,
              request_id: imageRequestId,
              negative_prompt: String(this.imageToolNegativePrompt || "").trim(),
              refine_prompt: true,
              image_style: styleKind,
              selected_loras: loras,
              model_family_override: modelFamily,
              style_preset_id: stylePresetId,
              steps,
              width: dims.width,
              height: dims.height,
              scene_subject: this.imageToolSubject || "",
            }
          );
        }
        const convo = payload?.conversation || null;
        if (convo && String(this.activeConversationId || "").trim() === conversationId) {
          this.activeConversation = convo;
          this.syncImagePrefsFromConversation(convo);
          this.$nextTick(() => this.scrollMessages());
        }
        this.imageToolLastPromptFinal = String(payload?.prompt_final || "").trim();
        this.imageToolPrompt = "";
        try {
          await this.refreshConversations();
          await this.refreshPanelBadges();
        } catch (_err) {}
      } catch (err) {
        if (this.isLikelyNetworkDropError(err)) {
          // Browser killed the long-running fetch — ComfyUI is still generating server-side.
          // Keep the thinking bubble alive; recoverMessageRequest will pick up the result.
        } else {
          this.imageToolError = String(err.message || err);
          this.imageToolPromptModalOpen = true;
          this.updateBodyClasses();
          this.setConversationSending(conversationId, false);
        }
      } finally {
        this.imageToolBusy = false;
        if (String(this.activeConversationId || "").trim() === conversationId) {
          this.$nextTick(() => this.scrollMessages());
        }
      }
    },

    async bgEnhance(img) {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId || !img?.filename) return;
      const key = img.filename;
      if (this.bgEnhanceBusy[key]) return;
      let requestId = "";
      try {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          requestId = String(window.crypto.randomUUID());
        }
      } catch (_e) {}
      if (!requestId) requestId = `bge_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      this.bgEnhanceBusy = { ...this.bgEnhanceBusy, [key]: true };
      this.setConversationSending(conversationId, {
        requestId,
        startedAt: Date.now(),
        cancelRequested: false,
        foraging: false,
        renderJob: true,
      });
      this.$nextTick(() => this.scrollMessages());
      try {
        const payload = await this.apiPost(
          `/api/conversations/${encodeURIComponent(conversationId)}/image-tool/bg-enhance`,
          { source_filename: img.filename, request_id: requestId }
        );
        const convo = payload?.conversation || null;
        if (convo && String(this.activeConversationId || "").trim() === conversationId) {
          this.activeConversation = convo;
          this.$nextTick(() => this.scrollMessages());
        }
        try { await this.refreshConversations(); } catch (_e) {}
        this.setConversationSending(conversationId, false);
      } catch (err) {
        if (this.isLikelyNetworkDropError(err)) {
          // Keep thinking bubble alive — recoverMessageRequest will pick up the result.
        } else {
          alert(`BG+ failed: ${err.message || err}`);
          this.setConversationSending(conversationId, false);
        }
      } finally {
        this.bgEnhanceBusy = { ...this.bgEnhanceBusy, [key]: false };
        this.$nextTick(() => this.scrollMessages());
      }
    },

    openVideoTool(img) {
      this.videoToolRefImage = img || null;
      this.videoToolPrompt = "";
      this.videoToolNegativePrompt = "";
      this.videoToolError = "";
      this.videoToolNumFrames = 81;
      this.videoToolOpen = true;
      this.updateBodyClasses();
    },

    closeVideoTool() {
      this.videoToolOpen = false;
      this.videoToolRefImage = null;
      this.videoToolError = "";
      this.updateBodyClasses();
    },

    async submitVideoToolGenerate() {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId || this.videoToolBusy) return;
      const prompt = String(this.videoToolPrompt || "").trim();
      if (!prompt) {
        this.videoToolError = "Motion prompt is required.";
        return;
      }
      const refFilename = String(
        this.videoToolRefImage?.filename || this.videoToolRefImage?.name || ""
      ).trim();
      if (!refFilename) {
        this.videoToolError = "Reference image is required.";
        return;
      }
      let requestId = "";
      try {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          requestId = String(window.crypto.randomUUID());
        }
      } catch (_e) {}
      if (!requestId) {
        requestId = `vidtool_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      }
      this.videoToolOpen = false;
      this.videoToolBusy = true;
      this.videoToolError = "";
      this.updateBodyClasses();
      this.setConversationSending(conversationId, {
        requestId,
        startedAt: Date.now(),
        cancelRequested: false,
        foraging: false,
        renderJob: true,
      });
      this.$nextTick(() => this.scrollMessages());
      try {
        const payload = await this.apiPost(
          `/api/conversations/${encodeURIComponent(conversationId)}/image-tool/video-generate`,
          {
            prompt,
            request_id: requestId,
            negative_prompt: String(this.videoToolNegativePrompt || "").trim(),
            ref_image_filename: refFilename,
            num_frames: this.videoToolNumFrames,
          }
        );
        const convo = payload?.conversation || null;
        if (convo && String(this.activeConversationId || "").trim() === conversationId) {
          this.activeConversation = convo;
          this.$nextTick(() => this.scrollMessages());
        }
        try {
          await this.refreshConversations();
          await this.refreshPanelBadges();
        } catch (_err) {}
      } catch (err) {
        if (this.isLikelyNetworkDropError(err)) {
          // Browser killed the long-running fetch — generation is still running server-side.
          // Keep the thinking bubble alive; recoverMessageRequest will pick up the result.
        } else {
          this.videoToolError = String(err.message || err);
          this.videoToolOpen = true;
          this.updateBodyClasses();
          this.setConversationSending(conversationId, false);
        }
      } finally {
        this.videoToolBusy = false;
        if (String(this.activeConversationId || "").trim() === conversationId) {
          this.$nextTick(() => this.scrollMessages());
        }
      }
    },

    openImagePicker(kind = "image") {
      const key = String(kind || "image").trim().toLowerCase();
      const node = key === "file" ? this.$refs.fileInput : this.$refs.imageInput;
      if (node && typeof node.click === "function") {
        node.click();
      }
      this.composerAddMenuOpen = false;
    },

    onComposerImagesPicked(event, kind = "") {
      const input = event?.target || null;
      const files = Array.from(input?.files || []);
      if (!files.length) {
        return;
      }
      const DOC_EXTS = new Set([".pdf", ".doc", ".docx", ".txt", ".md", ".csv"]);
      const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]);
      const DOC_ICONS = { ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".txt": "📃", ".md": "📃", ".csv": "📊" };
      const current = Array.isArray(this.composerImages) ? this.composerImages.slice() : [];
      const seen = new Set(current.map((x) => `${x.name}|${x.size}|${x.lastModified}`));
      for (const file of files) {
        if (!file) continue;
        if (current.length >= 4) break;
        const mime = String(file.type || "").toLowerCase();
        const extMatch = String(file.name || "").match(/\.[^.]+$/);
        const ext = extMatch ? extMatch[0].toLowerCase() : "";
        const mode = String(kind || "").trim().toLowerCase();
        const isImage = (mime.startsWith("image/") || IMAGE_EXTS.has(ext)) && mode !== "file";
        const isDoc = DOC_EXTS.has(ext) || ["application/pdf", "application/msword",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "text/plain", "text/markdown", "text/csv"].includes(mime);
        if (mode === "image" && !isImage) continue;
        if (mode === "file" && !isDoc) continue;
        if (mode !== "image" && mode !== "file" && !isImage && !isDoc) continue;
        const key = `${String(file.name || "")}|${Number(file.size || 0)}|${Number(file.lastModified || 0)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        current.push({
          id: `att_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
          file,
          name: String(file.name || (isDoc ? "document" : "image")).trim(),
          size: Number(file.size || 0),
          lastModified: Number(file.lastModified || 0),
          type: mime,
          isDoc,
          docIcon: isDoc ? (DOC_ICONS[ext] || "📄") : "",
          previewUrl: isImage ? URL.createObjectURL(file) : "",
        });
      }
      this.composerImages = current;
      this.saveComposerStateForConversation(this.activeConversationId);
      if (input) {
        input.value = "";
      }
    },

    removeComposerImage(imageId) {
      const current = Array.isArray(this.composerImages) ? this.composerImages.slice() : [];
      const next = [];
      for (const row of current) {
        if (String(row?.id || "") === String(imageId || "")) {
          if (row?.previewUrl) {
            URL.revokeObjectURL(row.previewUrl);
          }
          continue;
        }
        next.push(row);
      }
      this.composerImages = next;
      this.saveComposerStateForConversation(this.activeConversationId);
    },

    clearComposerImages() {
      const current = Array.isArray(this.composerImages) ? this.composerImages : [];
      for (const row of current) {
        if (row?.previewUrl) {
          URL.revokeObjectURL(row.previewUrl);
        }
      }
      this.composerImages = [];
      const input = this.$refs.imageInput;
      if (input) {
        input.value = "";
      }
      const fileInput = this.$refs.fileInput;
      if (fileInput) {
        fileInput.value = "";
      }
      this.saveComposerStateForConversation(this.activeConversationId);
    },

    initVoice() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return;
      this.voiceSupported = true;
      try {
        const rec = new SR();
        rec.lang = "en-US";
        rec.continuous = false;
        rec.interimResults = true;
        rec.onresult = (e) => {
          let final = "";
          let interim = "";
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            if (e.results[i].isFinal) { final += t; } else { interim += t; }
          }
          if (final) {
            this.draft = (this.draft ? this.draft + " " : "") + final.trim();
            this.$nextTick(() => this.resizeComposer());
          }
        };
        rec.onend = () => { this.voiceActive = false; };
        rec.onerror = () => { this.voiceActive = false; };
        this._voiceRecognition = rec;
      } catch (_e) {
        this.voiceSupported = false;
      }
    },

    toggleVoice() {
      const rec = this._voiceRecognition;
      if (!rec) return;
      if (this.voiceActive) {
        rec.stop();
        this.voiceActive = false;
      } else {
        try {
          rec.start();
          this.voiceActive = true;
        } catch (_e) {
          this.voiceActive = false;
        }
      }
    },

    speakText(text) {
      if (!this.ttsEnabled || !window.speechSynthesis) return;
      const plain = String(text || "")
        .replace(/```[\s\S]*?```/g, "code block")
        .replace(/`[^`]+`/g, "")
        .replace(/[*_#>~\[\]]/g, "")
        .replace(/https?:\/\/\S+/g, "link")
        .trim();
      if (!plain) return;
      window.speechSynthesis.cancel();
      const utt = new SpeechSynthesisUtterance(plain.slice(0, 2000));
      utt.rate = 1.0;
      window.speechSynthesis.speak(utt);
    },

    assistantMessageActions(msg) {
      const raw = String(msg?.content || "").trim();
      if (!raw) {
        return [];
      }
      const targets = extractAssistantActionTargets(raw);
      const actions = [];

      for (const id of targets.reflectionIds) {
        const action = {
          kind: "reflection_answer",
          id,
          label: `✓ Answer ${id.slice(0, 8)}`,
          style: "accent",
        };
        if (this.isQuickActionCompleted(action)) {
          action.label = "Answered";
          action.style = "subtle";
          action.completed = true;
        }
        actions.push(action);
      }

      for (const id of targets.pendingIds) {
        const answerAction = { kind: "pending_answer", id, label: "Answer", icon: "check", style: "ok" };
        if (this.isQuickActionCompleted(answerAction)) {
          answerAction.label = "Answered";
          answerAction.style = "subtle";
          answerAction.completed = true;
        }
        actions.push(answerAction);
        actions.push({ kind: "pending_ignore", id, label: "Ignore", icon: "x", style: "subtle" });
      }

      const isTalkMsg = String(msg?.mode || "") === "talk" || (!msg?.mode && !msg?.foraging);
      if (isTalkMsg) {
        for (const seed of (targets.forageSeeds || [])) {
          actions.push({
            kind: "forage_hint",
            id: seed,
            label: "Dig Deeper",
            title: "May need refreshed sources beyond model cutoff",
            icon: "search",
            style: "accent",
          });
        }
        // Waypoint lane is retired in this build; assistant messages no longer expose add-* actions.
      }

      const feedback = this.messageFeedbackState(msg);
      const isDown = feedback.rating === "down";
      actions.push({
        kind: "message_feedback",
        id: "up",
        rating: "up",
        label: "",
        title: "Helpful",
        icon: "thumb_up",
        style: feedback.rating === "up" ? "ok" : "subtle",
        selected: feedback.rating === "up",
      });
      actions.push({
        kind: "message_feedback",
        id: "down",
        rating: "down",
        label: "",
        title: isDown ? "Disregarded from context" : "Not helpful (disregard from context)",
        icon: "thumb_down",
        style: isDown ? "warn" : "subtle",
        selected: isDown,
      });

      actions.push({ kind: "reply_text", id: "", label: "Reply", icon: "reply", style: "subtle" });
      return actions;
    },

    messageFeedbackState(msg) {
      const row = msg && typeof msg === "object" ? msg : {};
      const feedback = row?.feedback && typeof row.feedback === "object" ? row.feedback : {};
      const meta = row?.meta && typeof row.meta === "object" ? row.meta : {};
      const rating = String(feedback?.rating || meta?.feedback_rating || "").trim().toLowerCase();
      const disregard = Boolean(feedback?.disregard || meta?.disregard_context);
      return {
        rating: rating === "up" || rating === "down" ? rating : "",
        disregard,
      };
    },

    messageActionKey(msg, action) {
      const msgKey = String(msg?.id || msg?.ts || "msg");
      const kind = String(action?.kind || "action");
      const id = String(action?.id || "");
      return `${msgKey}:${kind}:${id}`;
    },

    quickActionCompletionKey(action) {
      const kind = String(action?.kind || "").trim().toLowerCase();
      const id = String(action?.id || "").trim();
      if (!kind || !id) {
        return "";
      }
      return `${kind}:${id}`;
    },

    isQuickActionCompleted(action) {
      const key = this.quickActionCompletionKey(action);
      if (!key) {
        return false;
      }
      return Boolean(this.completedQuickActions?.[key]);
    },

    setQuickActionCompleted(action, completed = true) {
      const key = this.quickActionCompletionKey(action);
      if (!key) {
        return;
      }
      const next = Object.assign({}, this.completedQuickActions || {});
      if (completed) {
        next[key] = true;
      } else {
        delete next[key];
      }
      this.completedQuickActions = next;
    },

    isMessageActionBusy(msg, action) {
      const key = this.messageActionKey(msg, action);
      return Boolean(this.quickActionBusy?.[key]);
    },

    setMessageActionBusy(msg, action, busy) {
      const key = this.messageActionKey(msg, action);
      const next = Object.assign({}, this.quickActionBusy || {});
      if (busy) {
        next[key] = true;
      } else {
        delete next[key];
      }
      this.quickActionBusy = next;
    },

    _normalizeThinkStreamPayload(raw) {
      if (!raw || typeof raw !== "object") {
        return null;
      }
      const expiresAt = String(raw.expires_at || "").trim();
      const expiresMs = this._eventTimeMs(expiresAt);
      if (expiresMs > 0 && expiresMs < Date.now()) {
        return null;
      }
      const rows = Array.isArray(raw.events) ? raw.events : [];
      const events = rows
        .filter((row) => row && typeof row === "object")
        .map((row) => ({
          ts: String(row.ts || "").trim(),
          stage: String(row.stage || "").trim(),
          detail: String(row.detail || "").trim(),
        }))
        .filter((row) => row.ts || row.stage || row.detail)
        .slice(-64);
      if (!events.length) {
        return null;
      }
      const firstTs = this._eventTimeMs(events[0]?.ts);
      const lastTs = this._eventTimeMs(events[events.length - 1]?.ts);
      const storedDuration = Number(raw.duration_sec || raw.durationSec || 0);
      const durationSec = firstTs > 0 && lastTs >= firstTs
        ? (lastTs - firstTs) / 1000
        : (Number.isFinite(storedDuration) ? storedDuration : 0);
      return {
        events,
        durationSec: Number.isFinite(durationSec) ? durationSec : 0,
        started_at: String(raw.started_at || "").trim(),
        ended_at: String(raw.ended_at || "").trim(),
        expires_at: expiresAt,
      };
    },

    syncCompletedThinkStreamsFromConversation(conversation) {
      const next = Object.assign({}, this.completedThinkStreams || {});
      for (const key of Object.keys(next)) {
        const stream = next[key];
        const expiresMs = this._eventTimeMs(stream?.expires_at);
        if (expiresMs > 0 && expiresMs < Date.now()) {
          delete next[key];
        }
      }
      const convo = conversation && typeof conversation === "object" ? conversation : null;
      const messages = Array.isArray(convo?.messages) ? convo.messages : [];
      for (const msg of messages) {
        const role = String(msg?.role || "").trim().toLowerCase();
        const rid = String(msg?.request_id || "").trim();
        if (role !== "assistant" || !rid) {
          continue;
        }
        const payload = this._normalizeThinkStreamPayload(msg?.meta?.think_stream);
        if (!payload) {
          continue;
        }
        const existing = next[rid];
        if (!existing || !Array.isArray(existing.events) || existing.events.length < payload.events.length) {
          next[rid] = payload;
        }
      }
      this.completedThinkStreams = next;
    },

    applyConversationMessageUpdate(conversationId, updatedMessage) {
      const convoId = String(conversationId || "").trim();
      const messageId = String(updatedMessage?.id || "").trim();
      if (!convoId || !messageId) {
        return;
      }
      const applyToConversation = (conversation) => {
        if (!conversation || String(conversation.id || "").trim() !== convoId) {
          return conversation;
        }
        const rows = Array.isArray(conversation.messages) ? conversation.messages.slice() : [];
        const idx = rows.findIndex((row) => String(row?.id || "").trim() === messageId);
        if (idx < 0) {
          return conversation;
        }
        rows[idx] = Object.assign({}, rows[idx], updatedMessage);
        return Object.assign({}, conversation, { messages: rows });
      };
      this.activeConversation = applyToConversation(this.activeConversation);
      if (Array.isArray(this.conversations) && this.conversations.length) {
        this.conversations = this.conversations.map((row) => applyToConversation(row));
      }
    },

    seedReplyFromMessage(msg) {
      const raw = String(msg?.content || "").replace(/\s+/g, " ").trim();
      const excerpt = raw.length > 200 ? `${raw.slice(0, 197)}…` : raw;
      this.replyTargetMsg = {
        id: msg?.id || msg?.ts || "",
        role: msg?.role || "assistant",
        excerpt,
      };
      this.saveComposerStateForConversation(this.activeConversationId);
      this.$nextTick(() => {
        this.resizeComposer();
        const node = this.$refs.composerInput;
        if (node) node.focus();
      });
    },

    cancelReply() {
      this.replyTargetMsg = null;
      this.saveComposerStateForConversation(this.activeConversationId);
    },

    async runAssistantAction(msg, action) {
      if (!action || this.activeConversationSending) {
        return;
      }

      if (action.kind === "reply_text") {
        this.seedReplyFromMessage(msg);
        return;
      }

      if (action.kind === "forage_hint") {
        this.setComposerMode("forage");
        this.draft = action.id;
        this.$nextTick(() => {
          this.resizeComposer();
          const node = this.$refs.composerInput;
          if (node) {
            node.focus();
            const pos = String(this.draft || "").length;
            node.setSelectionRange(pos, pos);
          }
        });
        return;
      }

      if (action.kind === "message_feedback") {
        const conversationId = String(this.activeConversationId || "").trim();
        const messageId = String(msg?.id || "").trim();
        const rating = String(action?.rating || "").trim().toLowerCase();
        if (!conversationId || !messageId || !["up", "down"].includes(rating) || this.isMessageActionBusy(msg, action)) {
          return;
        }
        this.setMessageActionBusy(msg, action, true);
        try {
          const current = this.messageFeedbackState(msg).rating;
          const nextRating = current === rating ? "none" : rating;
          const payload = await this.apiPost(
            `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`,
            { rating: nextRating }
          );
          if (payload?.message && typeof payload.message === "object") {
            this.applyConversationMessageUpdate(conversationId, payload.message);
          }
        } catch (err) {
          window.alert(`Quick action failed: ${String(err.message || err)}`);
        } finally {
          this.setMessageActionBusy(msg, action, false);
        }
        return;
      }

      if (action.kind === "add_task" || action.kind === "add_event" || action.kind === "add_shopping" || action.kind === "add_routine") {
        throw new Error("Waypoint lane is not available in this Oathweaver build.");
      }

      if (action.completed || this.isQuickActionCompleted(action)) {
        return;
      }

      if (this.isMessageActionBusy(msg, action)) {
        return;
      }

      this.setMessageActionBusy(msg, action, true);
      try {
        if (action.kind === "reflection_answer") {
          const answer = String(
            window.prompt(`Answer reflection ${action.id}:`, "") || ""
          ).trim();
          if (!answer) {
            return;
          }
          const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(action.id)}/answer`, {
            answer,
          });
          this.setQuickActionCompleted(action, true);
          if (this.actionsOverlayOpen) {
            await this.refreshPendingActions();
          }
          await this.refreshPanelBadges();
          window.alert(payload.message || "Reflection answered.");
          return;
        }

        if (action.kind === "pending_answer") {
          const answer = String(window.prompt("Answer this pending action:", "") || "").trim();
          if (!answer) {
            return;
          }
          const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(action.id)}/answer`, {
            answer,
          });
          this.setQuickActionCompleted(action, true);
          if (this.actionsOverlayOpen) {
            await this.refreshPendingActions();
          }
          await this.refreshPanelBadges();
          window.alert(payload.message || "Action answered.");
          return;
        }

        if (action.kind === "pending_ignore") {
          const reason = String(window.prompt("Reason for ignore? (optional)", "") || "").trim();
          const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(action.id)}/ignore`, {
            reason,
          });
          if (this.actionsOverlayOpen) {
            await this.refreshPendingActions();
          }
          await this.refreshPanelBadges();
          window.alert(payload.message || "Action ignored.");
        }
      } catch (err) {
        window.alert(`Quick action failed: ${String(err.message || err)}`);
      } finally {
        this.setMessageActionBusy(msg, action, false);
      }
    },

    normalizeProjectSlug,

    formatDate(ts) {
      if (!ts) {
        return "";
      }
      const date = new Date(ts);
      if (Number.isNaN(date.getTime())) {
        return String(ts);
      }
      return date.toLocaleString();
    },

    formatMonthDay(ts) {
      if (!ts) {
        return "";
      }
      const date = new Date(ts);
      if (Number.isNaN(date.getTime())) {
        return "";
      }
      return `${date.getMonth() + 1}/${date.getDate()}`;
    },

    formatLastActiveLabel(ts) {
      const text = this.formatMonthDay(ts);
      if (!text) {
        return "Last active: just now";
      }
      return `Last active: ${text}`;
    },

    formatFileSize(bytes) {
      const value = Number(bytes || 0);
      if (!Number.isFinite(value) || value <= 0) {
        return "0 B";
      }
      const units = ["B", "KB", "MB", "GB"];
      let size = value;
      let idx = 0;
      while (size >= 1024 && idx < units.length - 1) {
        size /= 1024;
        idx += 1;
      }
      return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
    },

    defaultContentExpansion(nodes, maxDepth = 1) {
      const expanded = {};
      const walk = (items, depth) => {
        const rows = Array.isArray(items) ? items : [];
        for (const row of rows) {
          if (!row || row.type !== "dir") {
            continue;
          }
          const path = String(row.path || "").trim();
          if (!path) {
            continue;
          }
          const isOpen = depth <= maxDepth;
          expanded[path] = isOpen;
          if (isOpen && Array.isArray(row.children)) {
            walk(row.children, depth + 1);
          }
        }
      };
      walk(nodes, 0);
      return expanded;
    },

    contentPanelRows(project) {
      const rows = [
        {
          kind: "content_summary",
          project: String(project || this.activeProject || "general"),
          root: String(this.contentTreeRoot || ""),
          node_count: Number(this.contentTreeNodeCount || 0),
          truncated: Boolean(this.contentTreeTruncated),
        },
      ];
      const walk = (nodes, depth) => {
        const items = Array.isArray(nodes) ? nodes : [];
        for (const item of items) {
          const type = String(item?.type || "").trim().toLowerCase();
          const path = String(item?.path || "").trim();
          if (!path) {
            continue;
          }
          if (type === "dir") {
            const expanded = this.contentTreeExpanded[path] !== false;
            rows.push({
              kind: "content_dir",
              depth,
              name: String(item?.name || "").trim() || path,
              path,
              rel_path: String(item?.rel_path || "").trim(),
              child_count: Number(item?.child_count || 0),
              expanded,
            });
            if (expanded && Array.isArray(item.children)) {
              walk(item.children, depth + 1);
            }
            continue;
          }
          if (type === "file") {
            rows.push({
              kind: "content_file",
              depth,
              name: String(item?.name || "").trim() || path,
              path,
              rel_path: String(item?.rel_path || "").trim(),
              ext: String(item?.ext || "").trim(),
              size: Number(item?.size || 0),
            });
          }
        }
      };
      walk(this.contentTreeNodes, 0);
      return rows;
    },

    toggleContentTreeDir(row) {
      const path = String(row?.path || "").trim();
      if (!path) {
        return;
      }
      const next = Object.assign({}, this.contentTreeExpanded || {});
      next[path] = !Boolean(next[path] !== false);
      this.contentTreeExpanded = next;
      this.panelData = this.contentPanelRows(normalizeProjectSlug(this.activeProject));
    },

    openContentFile(row) {
      const path = String(row?.path || "").trim();
      if (!path) {
        return;
      }
      this.loadFileOverlay(path);
    },

    formatMsgTime(ts) {
      if (!ts) return "";
      const d = new Date(ts);
      if (Number.isNaN(d.getTime())) return "";
      return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    },

    async copyMsgToClipboard(msg) {
      let text = String(msg?.content || "").trim();
      if (String(msg?.role || "").trim().toLowerCase() === "assistant") {
        text = stripTrailingAssistantRule(text);
        const mode = String(msg?.mode || "").trim().toLowerCase();
        const isTalkLike = mode === "talk" || (!mode && !Boolean(msg?.foraging));
        if (isTalkLike) {
          text = normalizeTalkDisplayMarkdown(text);
        }
      }
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
      } catch (_err) {
        // Fallback for older browsers / non-HTTPS
        const ta = document.createElement("textarea");
        ta.value = text;
        Object.assign(ta.style, { position: "fixed", opacity: "0", pointerEvents: "none" });
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (_) {}
        document.body.removeChild(ta);
      }
      const key = String(msg?.id || msg?.ts || "");
      if (key) {
        this.msgCopiedId = key;
        setTimeout(() => { if (this.msgCopiedId === key) this.msgCopiedId = ""; }, 1800);
      }
    },

    withDayDividers(messages) {
      const result = [];
      let lastDay = null;
      for (const msg of messages) {
        const day = msg.ts ? toDateKey(new Date(msg.ts)) : null;
        if (day && day !== lastDay) {
          result.push({ _isDayMarker: true, day });
          lastDay = day;
        }
        result.push(msg);
      }
      return result;
    },

    sanitizeHomeCompanionName(raw) {
      return String(raw || "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 24);
    },

    async fetchHomeCompanionImages() {
      const total = Array.isArray(this.homeCompanionSketches) ? this.homeCompanionSketches.length : 0;
      if (total > 0) {
        try {
          const saved = parseInt(localStorage.getItem("oathweaver_companion_idx") || "0", 10);
          this.homeCompanionIndex = Number.isFinite(saved) && saved >= 0 ? saved % total : 0;
        } catch (_) {
          this.homeCompanionIndex = 0;
        }
      } else {
        this.homeCompanionIndex = 0;
      }
      try {
        const savedName = this.sanitizeHomeCompanionName(localStorage.getItem("oathweaver_companion_name") || "");
        this.homeCompanionName = savedName || HOME_COMPANION_DEFAULT_NAME;
      } catch (_) {
        this.homeCompanionName = HOME_COMPANION_DEFAULT_NAME;
      }
      this.homeCompanionNameDraft = this.homeCompanionName;
    },

    cycleHomeCompanionImage() {
      const total = Array.isArray(this.homeCompanionSketches) ? this.homeCompanionSketches.length : 0;
      if (!total) return;
      this.homeCompanionIndex = (this.homeCompanionIndex + 1) % total;
      try {
        localStorage.setItem("oathweaver_companion_idx", String(this.homeCompanionIndex));
      } catch (_) {}
    },

    startHomeCompanionRename() {
      this.homeCompanionRenaming = true;
      this.homeCompanionNameDraft = this.homeCompanionDisplayName;
      this.$nextTick(() => {
        const node = this.$refs.homeCompanionNameInput;
        if (node && typeof node.focus === "function") {
          node.focus();
          if (typeof node.select === "function") {
            node.select();
          }
        }
      });
    },

    saveHomeCompanionName() {
      const clean = this.sanitizeHomeCompanionName(this.homeCompanionNameDraft);
      this.homeCompanionName = clean || HOME_COMPANION_DEFAULT_NAME;
      this.homeCompanionNameDraft = this.homeCompanionName;
      this.homeCompanionRenaming = false;
      try {
        localStorage.setItem("oathweaver_companion_name", this.homeCompanionName);
      } catch (_) {}
    },

    cancelHomeCompanionRename() {
      this.homeCompanionRenaming = false;
      this.homeCompanionNameDraft = this.homeCompanionDisplayName;
    },

    sanitizeHomeWeatherLocation(raw) {
      return String(raw || "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 96);
    },

    parseHomeWeatherCoordinate(raw, min, max) {
      const text = String(raw ?? "").trim();
      if (!text) {
        return null;
      }
      const value = Number(text);
      if (!Number.isFinite(value)) {
        return null;
      }
      if (value < min || value > max) {
        return null;
      }
      return value;
    },

    blurActiveElement() {
      try {
        const active = document?.activeElement;
        if (active && typeof active.blur === "function") {
          active.blur();
        }
      } catch (_err) {}
    },

    loadHomeWeatherState() {
      try {
        const savedQuery = this.sanitizeHomeWeatherLocation(localStorage.getItem("oathweaver_home_weather_query") || "");
        const savedLabel = this.sanitizeHomeWeatherLocation(localStorage.getItem("oathweaver_home_weather_label") || "");
        const savedTimezone = String(localStorage.getItem("oathweaver_home_weather_timezone") || "").trim() || "auto";
        const savedLat = this.parseHomeWeatherCoordinate(localStorage.getItem("oathweaver_home_weather_lat"), -90, 90);
        const savedLon = this.parseHomeWeatherCoordinate(localStorage.getItem("oathweaver_home_weather_lon"), -180, 180);
        this.homeWeather.locationQuery = savedQuery;
        this.homeWeather.locationLabel = savedLabel;
        this.homeWeather.timezone = savedTimezone || "auto";
        this.homeWeather.latitude = savedLat;
        this.homeWeather.longitude = savedLon;
        this.homeWeatherLocationDraft = savedQuery || savedLabel || "";
      } catch (_err) {
        this.homeWeatherLocationDraft = "";
      }
    },

    persistHomeWeatherState() {
      try {
        localStorage.setItem("oathweaver_home_weather_query", String(this.homeWeather.locationQuery || ""));
        localStorage.setItem("oathweaver_home_weather_label", String(this.homeWeather.locationLabel || ""));
        localStorage.setItem("oathweaver_home_weather_timezone", String(this.homeWeather.timezone || "auto"));
        if (Number.isFinite(Number(this.homeWeather.latitude)) && Number.isFinite(Number(this.homeWeather.longitude))) {
          localStorage.setItem("oathweaver_home_weather_lat", String(this.homeWeather.latitude));
          localStorage.setItem("oathweaver_home_weather_lon", String(this.homeWeather.longitude));
        } else {
          localStorage.removeItem("oathweaver_home_weather_lat");
          localStorage.removeItem("oathweaver_home_weather_lon");
        }
      } catch (_err) {}
    },

    async geocodeHomeWeatherLocation(query) {
      const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&language=en&format=json`;
      const response = await fetch(url, { method: "GET" });
      if (!response.ok) {
        throw new Error(`Location lookup failed (${response.status})`);
      }
      const payload = await response.json();
      const rows = Array.isArray(payload?.results) ? payload.results : [];
      if (!rows.length) {
        throw new Error("Location not found.");
      }
      const top = rows[0] || {};
      const latitude = this.parseHomeWeatherCoordinate(top.latitude, -90, 90);
      const longitude = this.parseHomeWeatherCoordinate(top.longitude, -180, 180);
      if (latitude === null || longitude === null) {
        throw new Error("Location coordinates unavailable.");
      }
      const name = String(top.name || "").trim();
      const admin1 = String(top.admin1 || "").trim();
      const country = String(top.country || "").trim();
      const locationLabel = [name, admin1, country].filter(Boolean).join(", ");
      return {
        latitude,
        longitude,
        timezone: String(top.timezone || "auto").trim() || "auto",
        label: locationLabel || query,
      };
    },

    async reverseGeocodeHomeWeather(latitude, longitude) {
      const url =
        `https://geocoding-api.open-meteo.com/v1/reverse?latitude=${encodeURIComponent(latitude)}` +
        `&longitude=${encodeURIComponent(longitude)}&language=en&format=json`;
      const response = await fetch(url, { method: "GET" });
      if (!response.ok) {
        return "";
      }
      const payload = await response.json();
      const rows = Array.isArray(payload?.results) ? payload.results : [];
      if (!rows.length) {
        return "";
      }
      const top = rows[0] || {};
      const name = String(top.name || "").trim();
      const admin1 = String(top.admin1 || "").trim();
      const country = String(top.country || "").trim();
      return [name, admin1, country].filter(Boolean).join(", ");
    },

    async fetchHomeWeatherByCoordinates({ latitude, longitude, timezone = "auto" } = {}) {
      const lat = this.parseHomeWeatherCoordinate(latitude, -90, 90);
      const lon = this.parseHomeWeatherCoordinate(longitude, -180, 180);
      if (lat === null || lon === null) {
        throw new Error("Missing weather coordinates.");
      }
      const tz = String(timezone || "auto").trim() || "auto";
      const query =
        `latitude=${encodeURIComponent(lat)}` +
        `&longitude=${encodeURIComponent(lon)}` +
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day" +
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max" +
        "&temperature_unit=fahrenheit" +
        "&wind_speed_unit=mph" +
        `&timezone=${encodeURIComponent(tz)}` +
        "&forecast_days=1";
      const response = await fetch(`https://api.open-meteo.com/v1/forecast?${query}`, { method: "GET" });
      if (!response.ok) {
        throw new Error(`Weather fetch failed (${response.status})`);
      }
      const payload = await response.json();
      const current = payload?.current || {};
      const daily = payload?.daily || {};
      const dailyHigh = Array.isArray(daily.temperature_2m_max) ? Number(daily.temperature_2m_max[0]) : null;
      const dailyLow = Array.isArray(daily.temperature_2m_min) ? Number(daily.temperature_2m_min[0]) : null;
      const dailyPrecip = Array.isArray(daily.precipitation_probability_max) ? Number(daily.precipitation_probability_max[0]) : null;
      this.homeWeather.temperatureF = Number.isFinite(Number(current.temperature_2m)) ? Number(current.temperature_2m) : null;
      this.homeWeather.apparentF = Number.isFinite(Number(current.apparent_temperature)) ? Number(current.apparent_temperature) : null;
      this.homeWeather.weatherCode = Number.isFinite(Number(current.weather_code)) ? Number(current.weather_code) : null;
      this.homeWeather.windMph = Number.isFinite(Number(current.wind_speed_10m)) ? Number(current.wind_speed_10m) : null;
      this.homeWeather.isDay = Number.isFinite(Number(current.is_day)) ? Number(current.is_day) : null;
      this.homeWeather.highF = Number.isFinite(dailyHigh) ? dailyHigh : null;
      this.homeWeather.lowF = Number.isFinite(dailyLow) ? dailyLow : null;
      this.homeWeather.precipitationChance = Number.isFinite(dailyPrecip) ? dailyPrecip : null;
      this.homeWeather.timezone = String(payload?.timezone || tz || "auto").trim() || "auto";
      this.homeWeather.updatedAt = String(current.time || new Date().toISOString());
      this.homeWeather.error = "";
      this.homeWeather.latitude = lat;
      this.homeWeather.longitude = lon;
      this.persistHomeWeatherState();
    },

    async refreshHomeWeather(options = {}) {
      const silent = Boolean(options?.silent);
      if (silent && this.homeWeather.loading) {
        return;
      }
      if (!silent) {
        this.homeWeather.loading = true;
      }
      this.homeWeather.error = "";
      try {
        await this.fetchHomeWeatherByCoordinates({
          latitude: this.homeWeather.latitude,
          longitude: this.homeWeather.longitude,
          timezone: this.homeWeather.timezone || "auto",
        });
      } catch (err) {
        this.homeWeather.error = String(err?.message || err || "Unable to load weather.");
      } finally {
        this.homeWeather.loading = false;
      }
    },

    async saveHomeWeatherLocation() {
      const query = this.sanitizeHomeWeatherLocation(this.homeWeatherLocationDraft);
      if (!query) {
        this.homeWeather.error = "Enter a city or area name.";
        return;
      }
      this.homeWeather.loading = true;
      this.homeWeather.error = "";
      try {
        const row = await this.geocodeHomeWeatherLocation(query);
        this.homeWeather.locationQuery = query;
        this.homeWeather.locationLabel = row.label;
        this.homeWeather.latitude = row.latitude;
        this.homeWeather.longitude = row.longitude;
        this.homeWeather.timezone = row.timezone || "auto";
        this.homeWeatherLocationDraft = query;
        this.persistHomeWeatherState();
        await this.fetchHomeWeatherByCoordinates({
          latitude: row.latitude,
          longitude: row.longitude,
          timezone: row.timezone || "auto",
        });
        this.blurActiveElement();
        this.closeHomeWeatherPanel();
      } catch (err) {
        this.homeWeather.error = String(err?.message || err || "Unable to set weather location.");
      } finally {
        this.homeWeather.loading = false;
      }
    },

    async useCurrentLocationForWeather() {
      if (!navigator.geolocation) {
        this.homeWeather.error = "Device location is not supported in this browser.";
        return;
      }
      this.homeWeather.loading = true;
      this.homeWeather.error = "";
      try {
        const position = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: false,
            timeout: 12000,
            maximumAge: 300000,
          });
        });
        const latitude = this.parseHomeWeatherCoordinate(position?.coords?.latitude, -90, 90);
        const longitude = this.parseHomeWeatherCoordinate(position?.coords?.longitude, -180, 180);
        if (latitude === null || longitude === null) {
          throw new Error("Could not read device coordinates.");
        }
        const label = (await this.reverseGeocodeHomeWeather(latitude, longitude)) || "Current location";
        this.homeWeather.locationQuery = label;
        this.homeWeather.locationLabel = label;
        this.homeWeather.latitude = latitude;
        this.homeWeather.longitude = longitude;
        this.homeWeather.timezone = "auto";
        this.homeWeatherLocationDraft = label;
        this.persistHomeWeatherState();
        await this.fetchHomeWeatherByCoordinates({
          latitude,
          longitude,
          timezone: "auto",
        });
      } catch (err) {
        const message = String(err?.message || err || "").toLowerCase();
        if (message.includes("denied") || message.includes("permission")) {
          this.homeWeather.error = "Location permission was denied.";
        } else {
          this.homeWeather.error = String(err?.message || err || "Unable to get device location.");
        }
      } finally {
        this.homeWeather.loading = false;
      }
    },

    async initializeHomeWeather() {
      this.loadHomeWeatherState();
      if (
        Number.isFinite(Number(this.homeWeather.latitude)) &&
        Number.isFinite(Number(this.homeWeather.longitude))
      ) {
        await this.refreshHomeWeather({ silent: true });
      }
    },

    toggleHomeWeatherExpanded() {
      this.homeWeatherExpanded = !this.homeWeatherExpanded;
    },

    closeHomeWeatherPanel() {
      this.homeWeatherExpanded = false;
    },

    _updateHomeClock() {
      const now = new Date();
      const h = now.getHours();
      const m = now.getMinutes();
      const ampm = h >= 12 ? 'PM' : 'AM';
      const h12 = h % 12 || 12;
      this.homeCurrentTime = `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
    },

    refreshHomePhrase() {
      const pools = {
        morning: [
          "Morning. Let's make it count.",
          "A clear start leads to a sharp day.",
          "First hour sets the tone.",
          "Good morning. What's the one thing today?",
          "Start with intent, not inertia.",
          "Protect your first hour for what matters.",
          "Morning energy is finite. Use it well.",
          "What's worth your best focus this morning?",
          "Begin before distraction finds you.",
          "The morning is yours. Plan before it isn't.",
        ],
        afternoon: [
          "Midday checkpoint. How's the progress?",
          "Afternoon slump is real — one next step.",
          "Recalibrate. What still matters today?",
          "Halfway through. Finish what counts.",
          "Trim the list. Pick the two that matter.",
          "Energy dips here — do the easy wins now.",
          "Short sprint before the day softens.",
          "Review, refocus, keep going.",
          "Afternoon clarity often beats morning ambition.",
          "What can still be finished before evening?",
        ],
        evening: [
          "Good evening. Wind down with purpose.",
          "Capture what worked today.",
          "Evening is for closing loops.",
          "What's worth a quick note before you stop?",
          "Prep tomorrow while today is fresh.",
          "Good progress deserves acknowledgment.",
          "Reflect briefly, then disconnect.",
          "Evening review: done, pending, tomorrow.",
          "What's the one thing for tomorrow morning?",
          "Close clean. Start fresh.",
        ],
        night: [
          "Still up? Make it productive or make it restful.",
          "Night mode: deep work or full rest.",
          "Quiet hours are good for focus.",
          "Late nights are fine. Just be intentional.",
          "The list will still be there tomorrow.",
          "Night owls ship too.",
          "Dark outside. Good time to think.",
          "Capture the thought and get some sleep.",
          "Late focus is underrated.",
          "Whatever you're working on — make it worth the late hour.",
        ],
        day: [
          "Good systems feel quiet when they are working.",
          "Consistency is stronger than intensity over time.",
          "Done today is better than ideal next week.",
          "Clarity comes from action, not overthinking.",
          "Build less, finish more, repeat.",
          "Priorities become real when they get time blocks.",
          "Leave fewer loose ends than you found.",
          "Systems scale better than willpower.",
          "Ship the useful version, then refine.",
          "Default to progress you can sustain.",
        ],
      };
      const now = new Date();
      const windowKey = homePhraseWindowKey(now);
      const pool = pools[windowKey] || pools.day;
      const name = String(this.auth?.profile?.display_name || this.auth?.profile?.username || "owner").trim();
      const seedText = `${name}:${toDateKey(now)}:${windowKey}`;
      let seed = 0;
      for (let i = 0; i < seedText.length; i += 1) {
        seed = (seed * 31 + seedText.charCodeAt(i)) >>> 0;
      }
      const idx = seed % pool.length;
      this.homePhrase = pool[idx];
    },

    sanitizeHexColor(value, fallback = "#4285f4") {
      const text = String(value || "").trim();
      if (/^#[0-9a-fA-F]{6}$/.test(text)) {
        return text.toLowerCase();
      }
      return fallback;
    },

    isFourDigitPin(value) {
      const text = String(value || "").trim();
      return /^\d{4}$/.test(text);
    },

    canHardDelete(value) {
      const text = String(value || "")
        .trim()
        .replace(/\s+/g, " ")
        .toUpperCase();
      return text === "YES I AM SURE";
    },

    isLikelySavedAddress(value) {
      const text = String(value || "").trim();
      if (text.length < 8) {
        return false;
      }
      if (!/\d/.test(text)) {
        return false;
      }
      return (text.match(/[A-Za-z]/g) || []).length >= 4;
    },

    waypointContactDetailsPayload(form) {
      const row = form && typeof form === "object" ? form : {};
      const birthday = String(row.birthday || "").trim();
      const age = birthday ? "" : String(row.age || "").trim();
      return {
        notes: String(row.notes || "").trim(),
        nickname: String(row.nickname || "").trim(),
        birthday,
        age,
        age_is_estimate: !birthday && Boolean(row.age_is_estimate) && Boolean(age),
        gender: String(row.gender || "").trim(),
        school_or_work: String(row.school_or_work || "").trim(),
        likes: String(row.likes || "").trim(),
        dislikes: String(row.dislikes || "").trim(),
        important_dates: String(row.important_dates || "").trim(),
        medical_notes: String(row.medical_notes || "").trim(),
        email: String(row.email || "").trim(),
        phone: String(row.phone || "").trim(),
      };
    },

    waypointHasExtendedContactDetails(form) {
      const row = form && typeof form === "object" ? form : {};
      for (const key of PLANNER_CONTACT_DETAIL_KEYS) {
        if (key === "age_is_estimate") {
          continue;
        }
        if (String(row[key] || "").trim()) {
          return true;
        }
      }
      return false;
    },

    onWaypointContactBirthdayChanged() {
      if (!String(this.waypointContactForm?.birthday || "").trim()) {
        return;
      }
      this.waypointContactForm.age = "";
      this.waypointContactForm.age_is_estimate = false;
    },

    onWaypointMemberBirthdayChanged() {
      if (!String(this.waypointMemberForm?.birthday || "").trim()) {
        return;
      }
      this.waypointMemberForm.age = "";
      this.waypointMemberForm.age_is_estimate = false;
    },

    onWaypointMemberEditorBirthdayChanged() {
      if (!String(this.waypointMemberEditorForm?.birthday || "").trim()) {
        return;
      }
      this.waypointMemberEditorForm.age = "";
      this.waypointMemberEditorForm.age_is_estimate = false;
    },

    parseWaypointBuilderItems(raw) {
      const text = String(raw || "").trim();
      if (!text) {
        return [];
      }
      const rows = text
        .split(/\r?\n|,|;/)
        .map((x) => String(x || "").trim())
        .filter(Boolean)
        .slice(0, 30);
      const dedup = [];
      const seen = new Set();
      for (const row of rows) {
        const key = row.toLowerCase();
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        dedup.push(row);
      }
      return dedup;
    },

    async parseError(response, fallback) {
      let detail = "";
      try {
        const payload = await response.json();
        detail = payload.error || payload.description || payload.message || "";
      } catch (_err) {
        try {
          detail = (await response.text()).trim().slice(0, 200);
        } catch (_err2) {
          detail = "";
        }
      }
      return detail || fallback;
    },

    async apiRequest(method, path, data = null, requestOptions = null) {
      const timeoutMs = Number(requestOptions && requestOptions.timeoutMs || 0);
      const controller = timeoutMs > 0 ? new AbortController() : null;
      let timeoutId = null;
      const options = { method };
      if (data !== null) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(data || {});
      }
      if (controller) {
        options.signal = controller.signal;
        timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
      }
      let response = null;
      try {
        response = await fetch(path, options);
      } catch (err) {
        if (err && String(err.name || "").trim() === "AbortError" && timeoutMs > 0) {
          throw new Error(`${method} ${path} timed out (${timeoutMs}ms)`);
        }
        throw err;
      } finally {
        if (timeoutId !== null) {
          window.clearTimeout(timeoutId);
        }
      }
      if (response.status === 401) {
        this.auth.authenticated = false;
        this.auth.profile = null;
        throw new Error("Authentication required.");
      }
      if (!response.ok) {
        throw new Error(await this.parseError(response, `${method} ${path} failed (${response.status})`));
      }
      return response.json();
    },

    isLikelyNetworkDropError(err) {
      const msg = String(err && (err.message || err)).trim().toLowerCase();
      if (!msg) {
        return false;
      }
      return (
        msg.includes("load failed") ||
        msg.includes("failed to fetch") ||
        msg.includes("networkerror") ||
        msg.includes("network request failed") ||
        msg.includes("the internet connection appears to be offline")
      );
    },

    waitMs(ms) {
      const delay = Math.max(0, Number(ms || 0));
      return new Promise((resolve) => {
        window.setTimeout(resolve, delay);
      });
    },

    async recoverMessageRequest(conversationId, requestId, isForaging) {
      const convoId = String(conversationId || "").trim();
      const rid = String(requestId || "").trim();
      if (!convoId || !rid) {
        return false;
      }
      const maxWaitMs = isForaging ? 30 * 60 * 1000 : 20 * 60 * 1000;
      const pollMs = 2500;
      const deadline = Date.now() + maxWaitMs;
      while (Date.now() < deadline) {
        try {
          const jobPayload = await this.apiGet(`/api/jobs/${encodeURIComponent(rid)}`, { timeoutMs: 4500 });
          if (jobPayload && jobPayload.job && String(jobPayload.job.conversation_id || "").trim() !== convoId) {
            return false;
          }
          if (jobPayload && jobPayload.job) {
            const job = jobPayload.job;
            if (job.web_stack && Object.keys(job.web_stack).length > 0) {
              this.jobWebStack[rid] = job.web_stack;
            }
            if (Array.isArray(job.live_sources) && job.live_sources.length > 0) {
              const next = Object.assign({}, this.pendingLiveSources);
              next[convoId] = job.live_sources;
              this.pendingLiveSources = next;
            }
            if (Array.isArray(job.events) && job.events.length > 0) {
              const next = Object.assign({}, this.pendingJobEvents);
              next[convoId] = job.events;
              this.pendingJobEvents = next;
            }
            if (job.agent_tracker && typeof job.agent_tracker === "object") {
              const nextTracker = Object.assign({}, this.pendingJobAgentTracker);
              nextTracker[convoId] = job.agent_tracker;
              this.pendingJobAgentTracker = nextTracker;
            }
            const nextStage = Object.assign({}, this.sendingJobStage);
            nextStage[convoId] = { stage: job.stage || "", label: this._humanizeJobStage(job) };
            this.sendingJobStage = nextStage;
          }
        } catch (_jobErr) {
          // If job lookup fails, continue; request might still have completed and been persisted.
        }
        try {
          const payload = await this.apiGet(`/api/conversations/${encodeURIComponent(convoId)}`, { timeoutMs: 4500 });
          const convo = payload && payload.conversation ? payload.conversation : null;
          if (convo && Array.isArray(convo.messages)) {
            const hasAssistantReply = convo.messages.some(
              (row) => String(row?.role || "").trim().toLowerCase() === "assistant" && String(row?.request_id || "").trim() === rid
            );
              if (hasAssistantReply) {
                // Clear live source bubbles now that the reply has arrived
                if (this.pendingLiveSources[convoId]) {
                  const next = Object.assign({}, this.pendingLiveSources);
                  delete next[convoId];
                  this.pendingLiveSources = next;
                }
                if (this.pendingJobEvents[convoId]) {
                  const events = this.pendingJobEvents[convoId];
                  if (Array.isArray(events) && events.length && rid) {
                    const tracker = this.pendingJobAgentTracker[convoId];
                    const mergedEvents = this._mergePendingEventsWithTracker(events, tracker);
                    const streams = Object.assign({}, this.completedThinkStreams);
                    const keys = Object.keys(streams);
                    if (keys.length > 30) delete streams[keys[0]];
                    const startTs = mergedEvents[0]?.ts ? new Date(mergedEvents[0].ts).getTime() : 0;
                    const endTs = mergedEvents[mergedEvents.length - 1]?.ts ? new Date(mergedEvents[mergedEvents.length - 1].ts).getTime() : 0;
                    const durationSec = startTs && endTs ? ((endTs - startTs) / 1000).toFixed(1) : null;
                    streams[rid] = { events: mergedEvents, durationSec };
                    this.completedThinkStreams = streams;
                  }
                  const next = Object.assign({}, this.pendingJobEvents);
                  delete next[convoId];
                  this.pendingJobEvents = next;
                }
                if (this.pendingJobAgentTracker[convoId]) {
                  const nextTracker = Object.assign({}, this.pendingJobAgentTracker);
                  delete nextTracker[convoId];
                  this.pendingJobAgentTracker = nextTracker;
                }
                if (String(this.activeConversationId || "").trim() === convoId) {
                  this.activeConversation = convo;
                  this.activeConversationId = convo.id;
                  this.setActiveProject(convo.project || this.activeProject);
                  this.startAssistantTypewriterFromConversation(convo, rid);
                }
                try {
                  await this.refreshConversations();
                } catch (_refreshErr) {}
              try {
                await this.refreshPanelBadges();
              } catch (_refreshErr) {}
              return true;
            }
          }
        } catch (_convoErr) {
          // Keep polling until timeout.
        }
        await this.waitMs(pollMs);
      }
      return false;
    },

    isErrorEvent(event) {
      const stage = String(event?.stage || "").toLowerCase();
      return stage === "pipeline_error" || stage === "build_quality_gate_failed" || stage === "research_cancelled";
    },

    relativeEventTime(event, firstEvent) {
      try {
        const t0 = new Date(firstEvent?.ts || event?.ts).getTime();
        const t1 = new Date(event?.ts).getTime();
        const diff = (t1 - t0) / 1000;
        if (!isFinite(diff) || diff < 0) return "";
        return `+${this.formatDuration(diff, { alwaysHms: false })}`;
      } catch (_) { return ""; }
    },

    formatDuration(totalSeconds, opts = {}) {
      const alwaysHms = Boolean(opts?.alwaysHms);
      const raw = Number(totalSeconds);
      if (!Number.isFinite(raw) || raw < 0) {
        return "0s";
      }
      if (!alwaysHms && raw < 60) {
        return `${raw.toFixed(raw < 10 ? 1 : 0)}s`;
      }
      const whole = Math.floor(raw);
      const hours = Math.floor(whole / 3600);
      const minutes = Math.floor((whole % 3600) / 60);
      const seconds = whole % 60;
      if (hours > 0) {
        return `${hours}h ${minutes}m ${seconds}s`;
      }
      return `${minutes}m ${seconds}s`;
    },

    completedStreamDurationLabel(requestId) {
      const key = String(requestId || "").trim();
      if (!key) {
        return "0s";
      }
      const stream = this.completedThinkStreams?.[key];
      const events = Array.isArray(stream?.events) ? stream.events : [];
      const firstTs = this._eventTimeMs(events[0]?.ts);
      const lastTs = this._eventTimeMs(events[events.length - 1]?.ts);
      const fallbackSec = Number(stream?.durationSec || 0);
      const diffSec = firstTs > 0 && lastTs >= firstTs ? (lastTs - firstTs) / 1000 : fallbackSec;
      return this.formatDuration(diffSec, { alwaysHms: true });
    },

    _eventTimeMs(ts) {
      const value = new Date(ts || "").getTime();
      return Number.isFinite(value) && value > 0 ? value : 0;
    },

    _agentPersonaLabel(agent) {
      const raw = typeof agent === "object" ? String(agent?.persona || "") : String(agent || "");
      const text = raw.trim();
      if (!text) return "Agent";
      return text.replace(/_gap_fill$/i, " (gap fill)").replace(/_/g, " ");
    },

    _agentTrackerToEvents(tracker) {
      if (!tracker || typeof tracker !== "object") {
        return [];
      }
      const total = Number(tracker.total || 0);
      if (!Number.isFinite(total) || total <= 0) {
        return [];
      }
      const allAgents = Array.isArray(tracker.all_agents) ? tracker.all_agents : [];
      const active = Array.isArray(tracker.active) ? tracker.active : [];
      const done = Array.isArray(tracker.done) ? tracker.done : [];
      const activeCount = active.length;
      const doneCount = done.length;
      const pendingCount = Math.max(0, total - activeCount - doneCount);
      const allTimes = []
        .concat(active.map((row) => this._eventTimeMs(row?.started_at)))
        .concat(done.map((row) => this._eventTimeMs(row?.completed_at)))
        .filter((value) => value > 0);
      const firstTs = allTimes.length ? new Date(Math.min(...allTimes)).toISOString() : new Date().toISOString();
      const modeLabel = String(tracker.profile || "").trim().toLowerCase().includes("make") ? "Build" : "Research";
      const rows = [{
        ts: firstTs,
        stage: "agent_tracker_summary",
        detail: `${modeLabel} agents: ${doneCount}/${total} complete${activeCount ? ` · ${activeCount} active` : ""}${pendingCount ? ` · ${pendingCount} queued` : ""}`,
      }];

      const byNewestStart = active
        .slice()
        .sort((a, b) => this._eventTimeMs(a?.started_at) - this._eventTimeMs(b?.started_at));
      for (const row of byNewestStart) {
        const persona = this._agentPersonaLabel(row);
        const directive = String(row?.directive || "").trim().replace(/\s+/g, " ");
        const model = String(row?.model || "").trim();
        const detail = `${persona} running${directive ? ` — ${directive.slice(0, 100)}` : ""}${model ? ` (${model})` : ""}`;
        rows.push({
          ts: String(row?.started_at || firstTs),
          stage: "agent_tracker_active",
          detail,
        });
      }

      const byNewestDone = done
        .slice()
        .sort((a, b) => this._eventTimeMs(a?.completed_at) - this._eventTimeMs(b?.completed_at));
      for (const row of byNewestDone.slice(-6)) {
        const persona = this._agentPersonaLabel(row);
        const finding = String(row?.finding_preview || "").trim().replace(/\s+/g, " ");
        const state = row?.failed ? "failed" : "done";
        rows.push({
          ts: String(row?.completed_at || firstTs),
          stage: row?.failed ? "agent_tracker_done_failed" : "agent_tracker_done",
          detail: `${persona} ${state}${finding ? ` — ${finding.slice(0, 140)}` : ""}`,
        });
      }

      if (pendingCount > 0 && allAgents.length > 0) {
        const activeSet = new Set(
          active.map((row) => String((typeof row === "object" ? row?.persona : row) || "").trim()).filter(Boolean)
        );
        const doneSet = new Set(
          done.map((row) => String((typeof row === "object" ? row?.persona : row) || "").trim()).filter(Boolean)
        );
        const pendingNames = allAgents
          .map((row) => String((typeof row === "object" ? row?.persona : row) || "").trim())
          .filter((name) => name && !activeSet.has(name) && !doneSet.has(name))
          .slice(0, 2)
          .map((name) => this._agentPersonaLabel({ persona: name }));
        if (pendingNames.length) {
          const hidden = Math.max(0, pendingCount - pendingNames.length);
          rows.push({
            ts: firstTs,
            stage: "agent_tracker_pending",
            detail: `Queued next: ${pendingNames.join(", ")}${hidden ? ` (+${hidden})` : ""}`,
          });
        }
      }
      return rows;
    },

    _mergePendingEventsWithTracker(events, tracker) {
      const base = Array.isArray(events) ? events.filter((row) => row && typeof row === "object") : [];
      const trackerRows = this._agentTrackerToEvents(tracker);
      if (!trackerRows.length) {
        return base;
      }
      const merged = base.concat(trackerRows).map((row, idx) => ({
        idx,
        row,
        time: this._eventTimeMs(row.ts),
      }));
      merged.sort((a, b) => {
        if (a.time !== b.time) {
          return a.time - b.time;
        }
        return a.idx - b.idx;
      });
      const out = [];
      const seen = new Set();
      for (const item of merged) {
        const row = item.row;
        const key = `${String(row.ts || "")}|${String(row.stage || "")}|${String(row.detail || "")}`;
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        out.push(row);
      }
      return out.slice(-24);
    },

    _eventBranchKey(stage) {
      const s = String(stage || "").trim().toLowerCase();
      if (!s) return "processing";
      if (s.startsWith("message_") || s.startsWith("orchestrator_") || s === "lane_routed" || s === "talk_mode") return "routing";
      if (s.startsWith("web_")) return "web";
      if (s.includes("pool_started") || s.includes("foraging") || s.includes("building")) return "pool";
      if (s.includes("agent_")) return "agents";
      if (s.includes("synthesis") || s.includes("skeptic") || s.includes("gap_fill")) return "synthesis";
      if (s.includes("quality_gate") || s === "completed" || s === "done" || s.includes("cancel")) return "final";
      return "processing";
    },

    _eventBranchLabel(branch) {
      const map = {
        routing: "Routing",
        web: "Web Context",
        pool: "Pool Setup",
        agents: "Agent Steps",
        synthesis: "Synthesis",
        final: "Finalize",
        processing: "Processing",
      };
      return map[String(branch || "")] || "Processing";
    },

    _eventTreeDepth(stage) {
      const s = String(stage || "").trim().toLowerCase();
      if (!s) return 1;
      if (s.includes("agent_")) return 2;
      if (s.includes("quality_gate")) return 2;
      if (s.startsWith("web_source_")) return 2;
      return 1;
    },

    thinkTreeRows(requestId) {
      const key = String(requestId || "").trim();
      if (!key) return [];
      const stream = this.completedThinkStreams?.[key];
      const events = Array.isArray(stream?.events) ? stream.events : [];
      if (!events.length) return [];
      const rows = [];
      let lastBranch = "";
      for (const ev of events) {
        if (!ev || typeof ev !== "object") continue;
        const branch = this._eventBranchKey(ev.stage);
        if (branch !== lastBranch) {
          rows.push({
            kind: "branch",
            ts: ev.ts,
            stage: `branch_${branch}`,
            detail: this._eventBranchLabel(branch),
            depth: 0,
          });
          lastBranch = branch;
        }
        rows.push({
          kind: "event",
          ts: ev.ts,
          stage: ev.stage,
          detail: ev.detail,
          depth: this._eventTreeDepth(ev.stage),
        });
      }
      return rows;
    },

    toggleThinkTree(rid) {
      const key = String(rid || "").trim();
      if (!key) return;
      const next = Object.assign({}, this.expandedThinkTrees);
      next[key] = !next[key];
      this.expandedThinkTrees = next;
    },

    _startBlobAnimation(canvas) {
      if (!canvas || typeof canvas.getContext !== "function") return () => {};
      const ctx = canvas.getContext("2d");
      if (!ctx) return () => {};

      // Large blobs: rough positional anchors matching the CSS gradient blobs
      const LARGE = [
        { nx: 0.10, ny: 0.10, svx:  1.6, svy:  1.3, r: 0.32, c: [15, 162, 148], ph: 0.0 },
        { nx: 0.90, ny: 0.08, svx: -1.4, svy:  1.7, r: 0.28, c: [70, 178, 158], ph: 1.8 },
        { nx: 0.86, ny: 0.90, svx: -1.5, svy: -1.2, r: 0.30, c: [15, 155, 140], ph: 3.5 },
        { nx: 0.14, ny: 0.84, svx:  1.7, svy: -1.4, r: 0.25, c: [40, 168, 150], ph: 5.2 },
      ];
      // Small blobs: slightly cooler/brighter seafoam tones
      const SMALL = [
        { nx: 0.50, ny: 0.28, svx:  2.2, svy:  1.9, r: 0.09, c: [100, 210, 188], ph: 0.7 },
        { nx: 0.28, ny: 0.58, svx: -1.9, svy:  2.1, r: 0.07, c: [ 55, 200, 174], ph: 2.1 },
        { nx: 0.70, ny: 0.44, svx:  1.6, svy: -2.2, r: 0.08, c: [125, 215, 194], ph: 3.8 },
        { nx: 0.20, ny: 0.44, svx:  2.4, svy:  1.7, r: 0.06, c: [ 78, 204, 180], ph: 0.4 },
        { nx: 0.74, ny: 0.70, svx: -2.0, svy:  1.6, r: 0.07, c: [ 92, 200, 184], ph: 4.5 },
      ];

      let blobs = [];
      let animId = null;
      let lastT = 0;

      const resize = () => {
        const p = canvas.parentElement;
        if (!p) return;
        canvas.width  = p.clientWidth  || 800;
        canvas.height = p.clientHeight || 600;
        const w = canvas.width, h = canvas.height;
        const scale = Math.min(w, h);
        const spd = scale * 0.000028;
        blobs = [
          ...LARGE.map(d => ({ x: d.nx * w, y: d.ny * h, vx: d.svx * spd, vy: d.svy * spd, r: d.r, c: d.c, ph: d.ph, big: true  })),
          ...SMALL.map(d => ({ x: d.nx * w, y: d.ny * h, vx: d.svx * spd * 1.35, vy: d.svy * spd * 1.35, r: d.r, c: d.c, ph: d.ph, big: false })),
        ];
      };

      const drawBlob = (b, alpha) => {
        const s = Math.min(canvas.width, canvas.height);
        const rad = b.r * s;
        const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, rad);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${alpha})`);
        g.addColorStop(0.5, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${alpha * 0.35})`);
        g.addColorStop(1, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(b.x, b.y, rad, 0, Math.PI * 2);
        ctx.fill();
      };

      const drawThread = (x1, y1, x2, y2, t, ph) => {
        const dx = x2 - x1, dy = y2 - y1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 4) return;
        // Perpendicular unit vector (rotated 90°)
        const px = -dy / dist, py = dx / dist;
        // Sag: hangs under gravity, breathes with time
        const sag = dist * 0.22 * (1 + 0.14 * Math.sin(t * 0.00072 + ph));
        // Control point: midpoint shifted by sag perpendicular + gravity bias downward
        const cpx = (x1 + x2) * 0.5 + px * sag * 0.38;
        const cpy = (y1 + y2) * 0.5 + py * sag * 0.38 + sag * 0.55;
        // Taper: fade near endpoints
        const opacity = 0.18;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.quadraticCurveTo(cpx, cpy, x2, y2);
        ctx.strokeStyle = `rgba(15, 178, 158, ${opacity})`;
        ctx.lineWidth = 0.85;
        ctx.stroke();
        // Second fiber strand — very slight offset for woven look
        const off = 1.4;
        ctx.beginPath();
        ctx.moveTo(x1 + py * off, y1 - px * off);
        ctx.quadraticCurveTo(cpx + py * off - 1, cpy - px * off + 1, x2 + py * off, y2 - px * off);
        ctx.strokeStyle = `rgba(80, 200, 178, ${opacity * 0.55})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      };

      const frame = (t) => {
        const dt = lastT ? Math.min(t - lastT, 48) : 16;
        lastT = t;
        const w = canvas.width, h = canvas.height;
        const s = Math.min(w, h);
        ctx.clearRect(0, 0, w, h);

        // Update positions
        for (const b of blobs) {
          b.x += b.vx * dt;
          b.y += b.vy * dt;
          const margin = b.r * s * 0.28;
          if (b.x < margin)     { b.x = margin;     b.vx =  Math.abs(b.vx); }
          if (b.x > w - margin) { b.x = w - margin; b.vx = -Math.abs(b.vx); }
          if (b.y < margin)     { b.y = margin;     b.vy =  Math.abs(b.vy); }
          if (b.y > h - margin) { b.y = h - margin; b.vy = -Math.abs(b.vy); }
        }

        const large = blobs.filter(b => b.big);
        const small = blobs.filter(b => !b.big);

        // Draw large blobs
        for (const b of large) drawBlob(b, 0.15);

        ctx.save();
        ctx.globalCompositeOperation = "lighter";

        // Threads from each small blob to its nearest large blob
        for (const sb of small) {
          let nearest = large[0], nearD2 = Infinity;
          for (const lb of large) {
            const d2 = (sb.x - lb.x) ** 2 + (sb.y - lb.y) ** 2;
            if (d2 < nearD2) { nearD2 = d2; nearest = lb; }
          }
          const maxD = Math.min(w, h) * 0.85;
          if (Math.sqrt(nearD2) < maxD) {
            drawThread(sb.x, sb.y, nearest.x, nearest.y, t, sb.ph);
          }
        }

        ctx.restore();

        // Draw small blobs on top
        for (const b of small) drawBlob(b, 0.20);

        animId = requestAnimationFrame(frame);
      };

      resize();
      animId = requestAnimationFrame(frame);

      const ro = new ResizeObserver(() => { resize(); });
      if (canvas.parentElement) ro.observe(canvas.parentElement);

      return () => {
        if (animId) cancelAnimationFrame(animId);
        ro.disconnect();
      };
    },

    labelForEvent(event) {
      const detail = String(event?.detail || "").trim();
      if (detail) return detail;
      const stage = String(event?.stage || "").trim().toLowerCase();
      const fallbacks = {
        message_received: "Request received",
        orchestrator_ready: "Routing",
        orchestrator_received: "Understanding request",
        lane_routed: "Lane routed",
        attachment_analysis: "Reading attachments",
        attachment_analysis_done: "Attachments ready",
        talk_mode: "Generating reply",
        talk_mode_done: "Reply complete",
        web_research_started: "Starting web crawl",
        web_source_discovered: "Source discovered",
        web_stack_ready: "Web context ready",
        foraging_started: "Research started",
        foraging_yield_requested: "Yielding for chat",
        foraging_run: "Deploying the council",
        foraging_run_done: "Research complete",
        building_started: "Build started",
        research_pool_started: "Research pool starting",
        research_agent_started: "Agent starting",
        research_agent_completed: "Agent done",
        research_raw_written: "Notes collected",
        research_summary_written: "Synthesis written",
        build_pool_started: "Build pool starting",
        build_agent_started: "Build agent starting",
        build_agent_completed: "Build agent done",
        build_quality_gate_passed: "Quality gate passed",
        build_quality_gate_failed: "Quality gate failed",
        skeptic_pass_started: "Critique pass starting",
        skeptic_pass_completed: "Critique done",
        synthesizing: "Synthesizing",
        synthesis: "Synthesizing",
        gap_fill_started: "Filling gaps",
        gap_fill_completed: "Gap fill done",
        cancel_acknowledged: "Stopping",
        pipeline_error: "Error",
        completed: "Done",
        done: "Done",
      };
      return fallbacks[stage] || stage.replace(/_/g, " ");
    },

    _humanizeJobStage(job) {
      const stage = String(job?.stage || "").trim().toLowerCase();
      const tracker = job?.agent_tracker;
      const webStack = (job && typeof job.web_stack === "object" && job.web_stack) ? job.web_stack : {};
      const liveSources = Array.isArray(job?.live_sources) ? job.live_sources : [];
      const events = Array.isArray(job?.events) ? job.events : [];
      const lastEventDetail = events.length ? String(events[events.length - 1]?.detail || "").trim() : "";
      if (!stage || stage === "queued") return "Queued.";

      // Talk-mode stages
      if (stage === "message_received") return "Got it.";
      if (stage === "orchestrator_ready") return "Routing.";
      if (stage === "orchestrator_received") return "Understanding your request.";
      if (stage === "lane_routed") return "Intent routed.";
      if (stage === "attachment_analysis") return "Reading your files.";
      if (stage === "attachment_analysis_done") return "Files digested.";
      if (stage === "talk_mode") return "Drafting a reply.";
      if (stage === "web_research_started") return "Crawling the web.";
      if (stage === "web_source_discovered") {
        return liveSources.length > 0 ? `Crawling sources (${liveSources.length} found).` : "Crawling sources.";
      }
      if (stage === "web_stack_ready") {
        const sourceCount = Number(webStack?.source_count || 0);
        const crawlPages = Number(webStack?.crawl_pages || 0);
        if (sourceCount > 0 || crawlPages > 0) {
          return `Web context ready (${sourceCount} sources, ${crawlPages} pages).`;
        }
        return "Web context ready.";
      }
      if (stage === "talk_mode_done") return "Finishing up.";
      if (stage === "command_mode") return "Running command.";
      if (stage === "command_mode_done") return "Done.";
      if (stage === "pipeline_error") return "Hit a snag.";

      // Research kick-off
      if (stage === "foraging_started") return "Kicking off Research.";
      if (stage === "foraging_yield_requested") return "Stepping back temporarily.";
      if (stage === "foraging_run") return "Deploying the council.";
      if (stage === "foraging_run_done") return "Wrapping up.";
      if (stage === "foraging_paused") return "Paused.";

      // Agent lifecycle — use real tracker data
      if (stage === "research_pool_started") {
        const total = Number(tracker?.total || 0);
        const profile = String(tracker?.profile || "").trim().replace(/_/g, " ");
        if (total && profile) return `${total} agents deployed — ${profile}.`;
        if (total) return `${total} agents deployed.`;
        return "Deploying agents.";
      }
      if (stage === "research_agent_started") {
        const active = Array.isArray(tracker?.active) ? tracker.active : [];
        const done = Array.isArray(tracker?.done) ? tracker.done.length : 0;
        const total = Number(tracker?.total || 0);
        const names = active.slice(0, 2).map(a => {
          const p = typeof a === "object" ? String(a?.persona || "") : String(a);
          return p.replace(/_gap_fill$/, " (fill)").replace(/_/g, " ");
        });
        const progress = total ? ` — ${done}/${total} done` : "";
        if (names.length === 1) return `${names[0]}: on it${progress}.`;
        if (names.length >= 2) return `${names.join(" + ")}: on it${progress}.`;
        return `Agents working${progress}.`;
      }
      if (stage === "research_agent_completed") {
        const done = Array.isArray(tracker?.done) ? tracker.done.length : 0;
        const total = Number(tracker?.total || 0);
        const failed = Array.isArray(tracker?.done) ? tracker.done.filter(d => d?.failed).length : 0;
        const failNote = failed ? ` (${failed} weak)` : "";
        return total ? `${done}/${total} done${failNote}.` : "Agent done.";
      }
      if (stage === "research_raw_written") return "Notes collected.";
      if (stage === "research_summary_written") return "Synthesis written.";
      if (stage === "skeptic_pass_started") return "Running critique pass.";
      if (stage === "skeptic_pass_completed") return "Critique pass complete.";
      if (stage === "research_cancel_requested") return "Cancelling agents.";
      if (stage === "research_cancelled") return "Run cancelled.";

      // Gap fill
      if (stage === "gap_fill_started") return "Filling in the gaps.";
      if (stage === "gap_fill_completed") return "Gap fill done.";

      // Synthesis
      if (stage === "synthesizing" || stage === "synthesis") return "Synthesizing.";
      if (stage === "synthesis_unavailable") {
        return lastEventDetail ? `Synthesis unavailable: ${lastEventDetail}` : "Synthesis unavailable.";
      }

      // Terminal states
      if (stage === "cancel_requested" || stage === "cancel_acknowledged") return "Stopping.";
      if (stage === "completed" || stage === "done") return "Done.";

      return stage.replace(/_/g, " ") + ".";
    },

    apiGet(path, requestOptions = null) {
      return this.apiRequest("GET", path, null, requestOptions);
    },

    apiPost(path, data, requestOptions = null) {
      return this.apiRequest("POST", path, data, requestOptions);
    },

    async apiPostForm(path, formData) {
      const response = await fetch(path, { method: "POST", body: formData });
      if (response.status === 401) {
        this.auth.authenticated = false;
        this.auth.profile = null;
        throw new Error("Authentication required.");
      }
      if (!response.ok) {
        throw new Error(await this.parseError(response, `POST ${path} failed (${response.status})`));
      }
      return response.json();
    },

    apiPatch(path, data, requestOptions = null) {
      return this.apiRequest("PATCH", path, data, requestOptions);
    },

    apiPut(path, data, requestOptions = null) {
      return this.apiRequest("PUT", path, data, requestOptions);
    },

    apiDelete(path, requestOptions = null) {
      return this.apiRequest("DELETE", path, null, requestOptions);
    },

    async refreshPanelBadges() {
      const lastStatus = this.panelStatus ? { ...this.panelStatus } : null;
      const lastLessonsUnread = Number(this.lessonsUnreadCount || 0);
      const lastReflectionsUnread = Number(this.reflectionsUnreadCount || 0);
      try {
        const payload = await this.apiGet("/api/panel/status", { timeoutMs: 5000 });
        this.panelStatus = {
          pending_actions: Number(payload.pending_actions || 0),
          open_reflections: Number(payload.open_reflections || 0),
          learned_lessons: Number(payload.learned_lessons || 0),
          handoff_waiting_output: Number(payload.handoff_waiting_output || payload.pending_handoffs || 0),
          handoff_ready_for_ingest: Number(payload.handoff_ready_for_ingest || 0),
          pending_handoffs: Number(payload.pending_handoffs || 0),
          active_projects: Number(payload.active_projects || 0),
          web_mode: String(payload.web_mode || "auto"),
          cloud_mode: String(payload.cloud_mode || "off"),
          external_tools_mode: String(payload.external_tools_mode || "off"),
          open_external_requests: Number(payload.open_external_requests || 0),
          foraging_paused: Boolean(payload.foraging_paused),
          foraging_active_jobs: Number(payload.foraging_active_jobs || 0),
          foraging_yielding: Boolean(payload.foraging_yielding),
          foraging_completion_unread: Boolean(payload.foraging_completion_unread),
          building_paused: Boolean(payload.building_paused),
          building_active_jobs: Number(payload.building_active_jobs || 0),
          building_completion_unread: Boolean(payload.building_completion_unread),
          cards_unread: Number(payload.cards_unread || 0),
          watchtower_active: Number(payload.watchtower_active || 0),
          topics_with_research: Number(payload.topics_with_research || 0),
          forage_cards_pinned: Number(payload.forage_cards_pinned || 0),
          library_items_total: Number(payload.library_items_total || 0),
          library_items_pending: Number(payload.library_items_pending || 0),
        };
        await this.refreshLessonsUnreadCount();
        await this.refreshReflectionsUnreadCount();
      } catch (err) {
        // Keep last-known counters instead of clearing badges to zero during
        // transient backend stalls/errors.
        console.warn("refreshPanelBadges failed; preserving last known panel status:", err);
        if (lastStatus) {
          this.panelStatus = lastStatus;
        }
        if (Number.isFinite(lastLessonsUnread)) {
          this.lessonsUnreadCount = lastLessonsUnread;
        }
        if (Number.isFinite(lastReflectionsUnread)) {
          this.reflectionsUnreadCount = lastReflectionsUnread;
        }
      }
    },

    formatModeLabel(mode) {
      const key = String(mode || "").trim().toLowerCase();
      if (key === "off") {
        return "Off";
      }
      if (key === "auto") {
        return "Auto";
      }
      return "Ask";
    },

    async cycleWebMode() {
      this.chatMenuOpen = false;
      const order = ["off", "ask", "auto"];
      const current = String(this.panelStatus.web_mode || "auto").trim().toLowerCase();
      const idx = order.indexOf(current);
      const next = order[(idx + 1 + order.length) % order.length];
      try {
        const payload = await this.apiPost("/api/settings/web-mode", { mode: next });
        this.panelStatus.web_mode = String(payload.mode || next);
        await this.refreshPanelBadges();
        window.alert(
          `Live web research mode: ${this.formatModeLabel(this.panelStatus.web_mode)}\n` +
            "Off = never run web research. Ask = queue pending actions for your decision. Auto = run automatically and never ask permission."
        );
      } catch (err) {
        window.alert(`Could not change web mode: ${String(err.message || err)}`);
      }
    },

    async toggleForagingPause() {
      this.chatMenuOpen = false;
      try {
        const nextPaused = !Boolean(this.panelStatus.foraging_paused);
        const payload = await this.apiPost("/api/settings/foraging", { paused: nextPaused });
        this.panelStatus.foraging_paused = Boolean(payload.paused);
        this.panelStatus.foraging_active_jobs = Number(payload.active_jobs || this.panelStatus.foraging_active_jobs || 0);
        this.panelStatus.foraging_yielding = Boolean(payload.yielding);
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Could not update Research state: ${String(err.message || err)}`);
      }
    },

    async toggleBuildingPause() {
      this.chatMenuOpen = false;
      try {
        const nextPaused = !Boolean(this.panelStatus.building_paused);
        const payload = await this.apiPost("/api/settings/building", { paused: nextPaused });
        this.panelStatus.building_paused = Boolean(payload.paused);
        this.panelStatus.building_active_jobs = Number(payload.active_jobs || this.panelStatus.building_active_jobs || 0);
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Could not update Building state: ${String(err.message || err)}`);
      }
    },

    selectMakeType(typeId) {
      this.makeType = String(typeId || "").trim();
      localStorage.setItem("oathweaver_make_type", this.makeType);
      this.makeTypeModalOpen = false;
    },

    clearPendingMakeOutputExtension() {
      this.pendingExtendsRequestId = "";
      this.pendingExtendsTitle = "";
    },

    makeLabelForType(typeId) {
      const entry = this.makeTypeCatalog.find(e => e.type_id === typeId);
      return entry ? entry.label : String(typeId || "").replace(/_/g, " ");
    },

    async loadMakeTypeCatalog() {
      try {
        const payload = await this.apiGet("/api/make/catalog");
        if (Array.isArray(payload.catalog) && payload.catalog.length > 0) {
          this.makeTypeCatalog = payload.catalog;
        }
      } catch (err) {
        console.warn("Could not load Make type catalog:", err);
      }
    },

    async openMakeTypeModal() {
      this.makeTypeModalOpen = true;
      await this.loadMakeTypeCatalog();
    },

    async openMakeOutputEditModal() {
      const slug = String(this.activeConversationProjectSlug || "").trim();
      if (!slug) {
        return;
      }
      this.makeOutputEditModalOpen = true;
      this.updateBodyClasses();
      this.makeOutputEditLoading = true;
      this.makeOutputEditRows = [];
      try {
        const payload = await this.apiGet(`/api/projects/${encodeURIComponent(slug)}/make_outputs?limit=40`);
        this.makeOutputEditRows = Array.isArray(payload.outputs) ? payload.outputs : [];
      } catch (_err) {
        this.makeOutputEditRows = [];
      } finally {
        this.makeOutputEditLoading = false;
      }
    },

    closeMakeOutputEditModal() {
      this.makeOutputEditModalOpen = false;
      this.updateBodyClasses();
    },

    selectMakeOutputForEdit(row) {
      const selected = row && typeof row === "object" ? row : {};
      const requestId = String(selected.request_id || "").trim();
      if (!requestId) {
        return;
      }
      const makeType = String(selected.make_type || "").trim();
      const title = String(selected.title || selected.make_label || "").trim();
      this.pendingExtendsRequestId = requestId;
      this.pendingExtendsTitle = title;
      if (makeType) {
        this.makeType = makeType;
        localStorage.setItem("oathweaver_make_type", this.makeType);
      }
      this.closeMakeOutputEditModal();
    },

    closeActionsOverlay() {
      this.actionsOverlayOpen = false;
      this.updateBodyClasses();
    },

    closeSystemPanel() {
      this.panelOverlayOpen = false;
      this.panelLoading = false;
      this.panelKey = "";
      this.panelData = [];
      this.projectDetail = null;
      this.libraryDetailItem = null;
      this.updateBodyClasses();
    },

    closeAllOverlays() {
      this.chatMenuOpen = false;
      this.homeWeatherExpanded = false;
      this.waypointBuilderOpen = false;
      this.waypointCalendarMemberFilterOpen = false;
      this.swipeOpen = {};
      if (this.isMobileLayout()) {
        this.waypointChatExpanded = false;
      }
      this.closePostbagItem();
      this.closeLightbox();
      this.closeActionsOverlay();
      this.closeSystemPanel();
      this.closeMarkdownOverlay();
      this.closeTaskReminderDialog();
      this.closeImageToolPromptModal();
      this.closeImageToolStyleModal();
      this.closeVideoTool();
      this.closeAgentGraphModal();
      this.closeFamilyProfileModal();
      this.closeWebPushSettingsModal();
      this.closeEmailSettingsModal();
      this.closeMorningDigestModal();
      this.closeBotSettingsModal();
      this.closeProjectPickerModal();
      this.closeProjectBranchModal();
      this.closeProjectBuildTargetModal();
      this.closeProjectTopicTypeModal();
      this.closeLibraryIntakeModal();
      this.closeWaypointMemberEditor();
      this.closeTopicPickerModal();
      this.cancelUndergroundWarning();
      this.closeResetModal();
      this.closeWaypointEntryModals();
      this.makeTypeModalOpen = false;
      this.closeMakeOutputEditModal();
    },

    enforceStreamingOverlayPolicy() {
      if (!this.activeConversationSending) {
        return;
      }
      const anyOpen = Boolean(
        this.mdOverlayOpen ||
        this.actionsOverlayOpen ||
        this.panelOverlayOpen ||
        this.agentGraphModalOpen ||
        this.imageToolStyleModalOpen ||
        this.imageToolPromptModalOpen ||
        this.videoToolOpen ||
        this.projectPickerOpen ||
        this.projectBranchModalOpen ||
        this.projectTargetModalOpen ||
        this.projectTopicTypeModalOpen ||
        this.libraryIntakeOpen ||
        this.topicPickerOpen ||
        this.familyProfileModalOpen ||
        this.waypointMemberEditorOpen ||
        this.waypointTaskModalOpen ||
        this.waypointEventModalOpen ||
        this.waypointShoppingModalOpen ||
        this.waypointContactModalOpen ||
        this.webPushModalOpen ||
        this.emailSettingsModalOpen ||
        this.morningDigestModalOpen ||
        this.botSettingsModalOpen ||
        this.resetModalOpen ||
        this.undergroundWarningOpen ||
        this.postbagItemOpen ||
        this.lightboxOpen ||
        this.makeTypeModalOpen ||
        this.makeOutputEditModalOpen
      );
      if (!anyOpen) {
        return;
      }
      this.chatMenuOpen = false;
      this.homeWeatherExpanded = false;
      this.composerAddMenuOpen = false;
      this.mdOverlayOpen = false;
      this.actionsOverlayOpen = false;
      this.panelOverlayOpen = false;
      this.agentGraphModalOpen = false;
      this.imageToolStyleModalOpen = false;
      this.imageToolPromptModalOpen = false;
      this.videoToolOpen = false;
      this.projectPickerOpen = false;
      this.projectBranchModalOpen = false;
      this.projectTargetModalOpen = false;
      this.projectTopicTypeModalOpen = false;
      this.libraryIntakeOpen = false;
      this.topicPickerOpen = false;
      this.familyProfileModalOpen = false;
      this.waypointMemberEditorOpen = false;
      this.waypointTaskModalOpen = false;
      this.waypointEventModalOpen = false;
      this.waypointShoppingModalOpen = false;
      this.waypointContactModalOpen = false;
      this.webPushModalOpen = false;
      this.emailSettingsModalOpen = false;
      this.morningDigestModalOpen = false;
      this.botSettingsModalOpen = false;
      this.resetModalOpen = false;
      this.undergroundWarningOpen = false;
      this.undergroundWarningPendingTopic = null;
      this.postbagItemOpen = false;
      this.postbagItemData = null;
      this.lightboxOpen = false;
      this.lightboxUrl = "";
      this.lightboxName = "";
      this.makeTypeModalOpen = false;
      this.makeOutputEditModalOpen = false;
    },

    closeBlockingOverlaysForStreaming() {
      this.closeAllOverlays();
      this.enforceStreamingOverlayPolicy();
      this.updateBodyClasses();
    },

    isWorkspacePatchProposal(prop) {
      const actionType = String((prop && prop.action_type) || "").trim().toLowerCase();
      return actionType === "apply_patch" || actionType === "apply_patch_batch";
    },

    workspacePatchProposals() {
      return (Array.isArray(this.actionProposals) ? this.actionProposals : []).filter((prop) => this.isWorkspacePatchProposal(prop));
    },

    otherActionProposals() {
      return (Array.isArray(this.actionProposals) ? this.actionProposals : []).filter((prop) => !this.isWorkspacePatchProposal(prop));
    },

    patchProposalFiles(prop) {
      const payload = (prop && prop.action_payload) || {};
      if (Array.isArray(payload.files)) {
        return payload.files.filter((item) => item && typeof item === "object");
      }
      if (payload && payload.path) {
        return [payload];
      }
      return [];
    },

    patchProposalFileCount(prop) {
      return this.patchProposalFiles(prop).length;
    },

    patchProposalPreview(prop) {
      const files = this.patchProposalFiles(prop);
      if (!files.length) return "";
      const first = files[0] || {};
      const diffText = String(first.diff_text || "").trim();
      if (diffText) {
        return diffText.split("\n").slice(0, 14).join("\n");
      }
      const names = files.slice(0, 4).map((item) => String(item.path || item.rel_path || "").trim()).filter(Boolean);
      return names.join("\n");
    },

    patchProposalSummary(prop) {
      const payload = (prop && prop.action_payload) || {};
      return String(payload.summary || prop.text || prop.title || "").trim();
    },

    patchProposalKindLabel(prop) {
      const count = this.patchProposalFileCount(prop);
      return count > 1 ? `batch patch (${count})` : "patch";
    },

    async refreshPendingActions() {
      this.pendingActionsLoading = true;
      try {
        const payload = await this.apiGet("/api/pending-actions?limit=50", { timeoutMs: 5000 });
        this.pendingActions = Array.isArray(payload.pending_actions) ? payload.pending_actions : [];
        const apPayload = await this.apiGet("/api/action-proposals", { timeoutMs: 5000 });
        this.actionProposals = Array.isArray(apPayload.proposals) ? apPayload.proposals : [];
      } finally {
        this.pendingActionsLoading = false;
      }
    },

    pendingActionMode(item) {
      return "general";
    },

    pendingActionSystemHint(item) {
      return "";
    },

    actionTypeBadge(item) {
      const labels = {
        reflection: "Reflect",
        web_research: "Research",
        topic_review: "Memory",
        external_request: "External",
      };
      const kind = String(item?.type || "").trim().toLowerCase();
      return labels[kind] || kind || "Action";
    },

    pendingActionTitle(item) {
      const kind = String(item?.type || "").trim().toLowerCase();
      if (kind === "web_research") {
        return "Research Web Follow-up";
      }
      if (kind === "topic_review") {
        return "Memory Fact Review";
      }
      if (kind === "external_request") {
        const provider = String(item?.provider || "").trim();
        const intent = String(item?.intent || "").trim();
        if (provider && intent) {
          return `${provider} - ${intent}`;
        }
        if (provider) {
          return `${provider} request`;
        }
        return "External Request";
      }
      return String(item?.question || "Pending action");
    },

    watchScheduleLabel(row) {
      const schedule = String(row?.schedule || "manual").trim().toLowerCase();
      if (schedule === "daily") {
        const hour = Number(row?.schedule_hour);
        const safeHour = Number.isFinite(hour) ? Math.max(0, Math.min(23, Math.trunc(hour))) : 7;
        return `Daily at ${String(safeHour).padStart(2, "0")}:00 UTC`;
      }
      if (schedule === "hourly") {
        return "Hourly";
      }
      return "Manual";
    },

    relativeTimeLabel(ts) {
      const raw = String(ts || "").trim();
      if (!raw) return "never";
      const when = new Date(raw);
      if (Number.isNaN(when.getTime())) return this.formatDate(raw) || "unknown";
      const deltaSec = Math.floor((Date.now() - when.getTime()) / 1000);
      if (!Number.isFinite(deltaSec)) return this.formatDate(raw) || "unknown";
      if (deltaSec < 60) return "just now";
      if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
      if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
      if (deltaSec < 86400 * 14) return `${Math.floor(deltaSec / 86400)}d ago`;
      return this.formatDate(raw) || "unknown";
    },

    async addWatch(topic, profile, schedule, scheduleHour) {
      const t = String(topic || "").trim();
      if (!t) {
        window.alert("Topic is required.");
        return;
      }
      await this.apiPost("/api/watchtower/watches", {
        topic: t,
        profile: String(profile || "general"),
        schedule: String(schedule || "daily"),
        schedule_hour: Number(scheduleHour || 7),
      });
      this.watchtowerForm = { topic: "", profile: "general", schedule: "daily", schedule_hour: 7 };
      await this.refreshSystemPanel();
    },

    async deleteWatch(watchId) {
      if (!window.confirm("Remove this watch?")) return;
      await this.apiDelete(`/api/watchtower/watches/${encodeURIComponent(watchId)}`);
      await this.refreshSystemPanel();
    },

    async triggerWatch(watchId) {
      await this.apiPost(`/api/watchtower/watches/${encodeURIComponent(watchId)}/trigger`, {});
      window.alert("Watch queued. The research card will update when the run completes.");
      await this.refreshPanelBadges();
      if (this.panelKey === "watchtower") {
        await this.refreshSystemPanel();
      }
    },

    async toggleWatch(watchId, enabled) {
      await this.apiPut(`/api/watchtower/watches/${encodeURIComponent(watchId)}`, { enabled });
      await this.refreshSystemPanel();
    },

    async approveActionProposal(id) {
      await this.apiPost(`/api/action-proposals/${encodeURIComponent(id)}/approve`, {});
      await this.refreshPendingActions();
      await this.refreshPanelBadges();
    },

    async rejectActionProposal(id) {
      await this.apiPost(`/api/action-proposals/${encodeURIComponent(id)}/reject`, {});
      await this.refreshPendingActions();
      await this.refreshPanelBadges();
    },
    async openPendingActions() {
      if (this.activeConversationSending) {
        return;
      }
      this.chatMenuOpen = false;
      this.panelOverlayOpen = false;
      this.setActiveApp("chat");
      if (this.isMobileLayout()) {
        this.closeSidebar();
      }
      this.actionsOverlayOpen = true;
      this.updateBodyClasses();
      try {
        await this.refreshPendingActions();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Postbag load failed: ${String(err.message || err)}`);
      }
    },

    async handlePendingAction(actionId, actionType, presetAnswer = "") {
      if (!actionId || !actionType) {
        return;
      }

      if (actionType === "ignore") {
        const reason = window.prompt("Reason for ignoring this pending action? (optional)", "") || "";
        const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(actionId)}/ignore`, { reason });
        await this.refreshPendingActions();
        await this.refreshPanelBadges();
        window.alert(payload.message || "Action ignored.");
        return;
      }

      if (actionType === "codex") {
        const note = window.prompt("Optional note to include for Codex:", "") || "";
        const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(actionId)}/codex`, { note });
        await this.refreshPendingActions();
        await this.refreshPanelBadges();
        window.alert(payload.message || "Sent to Codex inbox.");
        return;
      }

      if (actionType === "topic_yes" || actionType === "topic_no") {
        const accepted = actionType === "topic_yes";
        try {
          await this.apiPost(`/api/memory/reviews/${encodeURIComponent(actionId)}/answer`, { accepted });
          await this.refreshPendingActions();
          await this.refreshPanelBadges();
        } catch (err) {
          window.alert(`Memory update failed: ${err.message || err}`);
        }
        return;
      }

      if (actionType === "answer") {
        let answer = String(presetAnswer || "").trim();
        if (!answer) {
          answer = window.prompt("Answer this action directly:", "") || "";
        }
        if (!answer.trim()) {
          return;
        }
        const payload = await this.apiPost(`/api/pending-actions/${encodeURIComponent(actionId)}/answer`, {
          answer: answer,
        });
        await this.refreshPendingActions();
        await this.refreshPanelBadges();
        window.alert(payload.message || "Action answered.");
      }
    },

    async refreshSystemPanel() {
      if (!this.panelKey) {
        return;
      }
      this.panelLoading = true;
      try {
        if (this.panelKey === "reflections") {
          const payload = await this.apiGet("/api/panel/reflections-history?limit=120");
          this.panelData = Array.isArray(payload.reflections) ? payload.reflections : [];
          this.markReflectionsAsRead(this.panelData);
          return;
        }
        if (this.panelKey === "lessons") {
          const payload = await this.apiGet("/api/panel/lessons?limit=80&sort=newest");
          this.panelData = Array.isArray(payload.lessons) ? payload.lessons : [];
          this.markLessonsAsRead(this.panelData);
          return;
        }
        if (this.panelKey === "handoffs") {
          const payload = await this.apiGet("/api/panel/handoffs?limit=40");
          this.panelData = Array.isArray(payload.handoffs) ? payload.handoffs : [];
          return;
        }
        if (this.panelKey === "projects") {
          const payload = await this.apiGet("/api/panel/projects?limit=80");
          this.panelData = Array.isArray(payload.projects) ? payload.projects : [];
          return;
        }
        if (this.panelKey === "foraging") {
          const payload = await this.apiGet("/api/panel/foraging?limit=80&mark_read=1");
          const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
          this.panelData = jobs;
          if (payload.foraging && typeof payload.foraging === "object") {
            this.panelStatus.foraging_paused = Boolean(payload.foraging.paused);
            this.panelStatus.foraging_active_jobs = Number(payload.foraging.active_jobs || 0);
            this.panelStatus.foraging_yielding = Boolean(payload.foraging.yielding);
            this.panelStatus.foraging_completion_unread = Boolean(payload.foraging.completion_unread);
          }
          return;
        }
        if (this.panelKey === "building") {
          const payload = await this.apiGet("/api/panel/building?limit=80&mark_read=1");
          const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
          this.panelData = jobs;
          if (payload.building && typeof payload.building === "object") {
            this.panelStatus.building_paused = Boolean(payload.building.paused);
            this.panelStatus.building_active_jobs = Number(payload.building.active_jobs || 0);
            this.panelStatus.building_completion_unread = Boolean(payload.building.completion_unread);
          }
          return;
        }
        if (this.panelKey === "project_detail") {
          const project = normalizeProjectSlug(this.activeProject);
          const payload = await this.apiGet(
            `/api/projects/${encodeURIComponent(project)}/details?events=80&artifacts=40`
          );
          const summary = payload.summary || {};
          const artifacts = Array.isArray(payload.artifacts) ? payload.artifacts : [];
          const events = Array.isArray(payload.events) ? payload.events : [];
          const handoffs = Array.isArray(payload.handoffs) ? payload.handoffs : [];
          this.projectDetail = payload;
          this.panelData = [
            { kind: "summary", ...summary, project },
            ...artifacts.map((path) => ({ kind: "artifact", path })),
            ...events
              .slice(-20)
              .reverse()
              .map((item) => ({
                kind: "event",
                ts: item.ts,
                actor: item.actor,
                event: item.event,
                detail: JSON.stringify(item.details || {}),
              })),
            ...handoffs.slice(0, 12).map((item) => ({ kind: "handoff", ...item })),
          ];
          return;
        }
        if (this.panelKey === "content") {
          const project = normalizeProjectSlug(this.activeProject);
          const payload = await this.apiGet(
            `/api/projects/${encodeURIComponent(project)}/content-tree?depth=6&nodes=1800`
          );
          this.contentTreeRoot = String(payload.root || "");
          this.contentTreeNodes = Array.isArray(payload.tree) ? payload.tree : [];
          this.contentTreeNodeCount = Number(payload.node_count || 0);
          this.contentTreeTruncated = Boolean(payload.truncated);
          if (this._contentTreeProject !== project) {
            this.contentTreeExpanded = this.defaultContentExpansion(this.contentTreeNodes, 1);
          } else if (!Object.keys(this.contentTreeExpanded || {}).length) {
            this.contentTreeExpanded = this.defaultContentExpansion(this.contentTreeNodes, 1);
          }
          this._contentTreeProject = project;
          this.panelData = this.contentPanelRows(project);
          return;
        }
        if (this.panelKey === "outbox") {
          const payload = await this.apiGet("/api/panel/outbox?limit=80");
          this.panelData = Array.isArray(payload.outbox) ? payload.outbox : [];
          return;
        }
        if (this.panelKey === "watchtower") {
          const payload = await this.apiGet("/api/watchtower/watches");
          this.panelData = Array.isArray(payload.watches) ? payload.watches : [];
          return;
        }
        if (this.panelKey === "library") {
          const payload = await this.apiGet("/api/panel/library?limit=150");
          this.panelData = payload && typeof payload === "object" ? payload : { items: [], counts: {}, topics: [], projects: [] };
          return;
        }
        if (this.panelKey === "library_detail") {
          const itemId = String(this.libraryDetailItem?.id || "").trim();
          if (!itemId) {
            this.libraryDetailItem = null;
            this.panelData = {};
            return;
          }
          const payload = await this.apiGet(`/api/library/${encodeURIComponent(itemId)}`);
          this.libraryDetailItem = payload?.item
            ? { ...payload.item, _summary_html: markdownToHtml(String(payload.item.summary_markdown || "")) }
            : null;
          this.panelData = payload?.item || {};
          return;
        }
        if (this.panelKey === "forage-cards") {
          const payload = await this.apiGet("/api/forage-cards?limit=50");
          this.panelData = Array.isArray(payload.cards) ? payload.cards : [];
          return;
        }
        if (this.panelKey === "topics") {
          const payload = await this.apiGet("/api/topics");
          this.panelData = { topics: Array.isArray(payload.topics) ? payload.topics : [] };
          return;
        }
        if (this.panelKey === "topic_detail") {
          const topicId = String(this._activePanelTopicId || "").trim();
          if (!topicId) { this.topicDetailData = null; return; }
          const payload = await this.apiGet(`/api/topics/${encodeURIComponent(topicId)}/detail`);
          this.topicDetailData = payload && !payload.error ? payload : null;
          this.panelData = {};
          return;
        }
        if (this.panelKey === "system") {
          await this.applyFontConfig();
          this.panelData = {};
          return;
        }
        this.panelData = [];
      } finally {
        this.panelLoading = false;
      }
    },

    async openGrowthPanel() {
      if (this.activeConversationSending) {
        return;
      }
      this.chatMenuOpen = false;
      this.actionsOverlayOpen = false;
      this.setActiveApp("chat");
      this.panelKey = "growth";
      this.panelOverlayOpen = true;
      this.updateBodyClasses();
      if (this.isMobileLayout()) this.closeSidebar();
      try {
        const [postbagPayload, reflectionsPayload, lessonsPayload] = await Promise.all([
          this.apiGet("/api/pending-actions?limit=50"),
          this.apiGet("/api/panel/reflections-history?limit=60"),
          this.apiGet("/api/panel/lessons?limit=40&sort=newest"),
        ]);
        this.growthPostbagRows = Array.isArray(postbagPayload?.actions) ? postbagPayload.actions : [];
        this.growthReflectionsRows = Array.isArray(reflectionsPayload?.reflections) ? reflectionsPayload.reflections : [];
        this.growthLessonsRows = Array.isArray(lessonsPayload?.lessons) ? lessonsPayload.lessons : [];
        this.markReflectionsAsRead(this.growthReflectionsRows);
        this.markLessonsAsRead(this.growthLessonsRows);
      } catch (_err) {
        this.growthPostbagRows = [];
        this.growthReflectionsRows = [];
        this.growthLessonsRows = [];
      }
    },

    switchGrowthTab(tab) {
      this.growthActiveTab = tab;
    },

    async openSystemPanel(panelKey) {
      if (this.activeConversationSending) {
        return;
      }
      let key = String(panelKey || "").trim().toLowerCase();
      if (!["foraging", "building", "reflections", "lessons", "handoffs", "outbox", "projects", "project_detail", "content", "watchtower", "library", "library_detail", "forage-cards", "topics", "topic_detail", "system"].includes(key)) {
        return;
      }
      this.chatMenuOpen = false;
      this.actionsOverlayOpen = false;
      this.setActiveApp("chat");
      if (key === "lessons") {
        this.lessonsViewMode = "current";
      }
      this.panelKey = key;
      this.panelData = [];
      this.panelOverlayOpen = true;
      this.updateBodyClasses();
      if (this.isMobileLayout()) {
        this.closeSidebar();
      }
      try {
        await this.refreshSystemPanel();
        await this.refreshPanelBadges();
      } catch (err) {
        this.panelData = [];
        window.alert(`Panel load failed: ${String(err.message || err)}`);
      }
    },

    openLibraryIntakeModal() {
      this.chatMenuOpen = false;
      this.libraryIntakeOpen = true;
      this.libraryIntakeSubmitting = false;
      this.libraryIntakeError = "";
      this.libraryIntakeFiles = [];
      this.libraryIntakeTitle = "";
      this.libraryIntakeSourceKind = "general";
      this.libraryIntakeDomain = "";
      this.libraryIntakeTopicId = String(this.activeTopicId || "").trim() === "general" ? "" : String(this.activeTopicId || "").trim();
      this.libraryIntakeProjectSlug = normalizeProjectSlug(this.activeProject) === "general" ? "" : normalizeProjectSlug(this.activeProject);
      this.updateBodyClasses();
    },

    closeLibraryIntakeModal() {
      this.libraryIntakeOpen = false;
      this.libraryIntakeSubmitting = false;
      this.libraryIntakeError = "";
      this.libraryIntakeFiles = [];
      if (this.$refs.libraryFileInput) {
        this.$refs.libraryFileInput.value = "";
      }
      this.updateBodyClasses();
    },

    onLibraryFilesSelected(event) {
      const files = Array.from(event?.target?.files || []);
      this.libraryIntakeFiles = files;
      this.libraryIntakeError = "";
    },

    async submitLibraryIntake() {
      if (this.libraryIntakeSubmitting) {
        return;
      }
      const files = Array.isArray(this.libraryIntakeFiles) ? this.libraryIntakeFiles : [];
      if (!files.length) {
        this.libraryIntakeError = "Choose at least one document.";
        return;
      }
      this.libraryIntakeSubmitting = true;
      this.libraryIntakeError = "";
      try {
        const formData = new FormData();
        formData.append("source_kind", String(this.libraryIntakeSourceKind || "general").trim() || "general");
        if (String(this.libraryIntakeTitle || "").trim()) {
          formData.append("title", String(this.libraryIntakeTitle || "").trim());
        }
        if (String(this.libraryIntakeDomain || "").trim()) {
          formData.append("domain", String(this.libraryIntakeDomain || "").trim());
        }
        if (String(this.libraryIntakeTopicId || "").trim()) {
          formData.append("topic_id", String(this.libraryIntakeTopicId || "").trim());
        }
        if (String(this.libraryIntakeProjectSlug || "").trim()) {
          formData.append("project_slug", normalizeProjectSlug(this.libraryIntakeProjectSlug));
        }
        for (const file of files) {
          formData.append("files", file, file.name || "document");
        }
        const payload = await this.apiPostForm("/api/library/intake", formData);
        const errors = Array.isArray(payload?.errors) ? payload.errors.filter(Boolean) : [];
        const imported = Array.isArray(payload?.items) ? payload.items.length : 0;
        if (errors.length && !imported) {
          this.libraryIntakeError = errors.join("\n");
          return;
        }
        if (errors.length) {
          window.alert(`Imported ${imported} item(s). Some files were skipped:\n\n${errors.join("\n")}`);
        }
        this.closeLibraryIntakeModal();
        if (this.panelKey === "library") {
          await this.refreshSystemPanel();
        }
        await this.refreshPanelBadges();
      } catch (err) {
        this.libraryIntakeError = String(err.message || err);
      } finally {
        this.libraryIntakeSubmitting = false;
      }
    },

    async openLibraryDetail(row) {
      const itemId = String(row?.id || "").trim();
      if (!itemId) {
        return;
      }
      this.libraryDetailItem = { ...(row || {}) };
      await this.openSystemPanel("library_detail");
    },

    async saveLibraryDetail() {
      const itemId = String(this.libraryDetailItem?.id || "").trim();
      if (!itemId) {
        return;
      }
      try {
        const payload = await this.apiPatch(`/api/library/${encodeURIComponent(itemId)}`, {
          title: String(this.libraryDetailItem?.title || "").trim(),
          source_kind: String(this.libraryDetailItem?.source_kind || "general").trim(),
          topic_id: String(this.libraryDetailItem?.topic_id || "").trim(),
          project_slug: String(this.libraryDetailItem?.project_slug || "").trim(),
        });
        this.libraryDetailItem = payload?.item
          ? { ...payload.item, _summary_html: markdownToHtml(String(payload.item.summary_markdown || "")) }
          : this.libraryDetailItem;
        this.panelData = this.libraryDetailItem || {};
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert("Save failed: " + String(err.message || err));
      }
    },

    async deleteLibraryDetail() {
      const itemId = String(this.libraryDetailItem?.id || "").trim();
      if (!itemId) {
        return;
      }
      if (!window.confirm("Delete this Library item?")) {
        return;
      }
      try {
        await this.apiDelete(`/api/library/${encodeURIComponent(itemId)}`);
        this.libraryDetailItem = null;
        await this.openSystemPanel("library");
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert("Delete failed: " + String(err.message || err));
      }
    },

    async openLibraryMarkdown(row = null) {
      if (this.activeConversationSending) {
        return;
      }
      const itemId = String((row || this.libraryDetailItem)?.id || "").trim();
      if (!itemId) {
        return;
      }
      try {
        const payload = await this.apiGet(`/api/library/${encodeURIComponent(itemId)}/markdown`);
        this.mdTitle = String((row || this.libraryDetailItem)?.title || payload?.name || "Library Markdown");
        this.mdPath = String(payload?.path || "");
        this.mdHtml = markdownToHtml(String(payload?.content || ""));
        this.mdOverlayOpen = true;
        this.updateBodyClasses();
      } catch (err) {
        window.alert("Could not load markdown: " + String(err.message || err));
      }
    },

    openLibrarySource(row = null) {
      const itemId = String((row || this.libraryDetailItem)?.id || "").trim();
      if (!itemId) {
        return;
      }
      window.open(`/api/library/${encodeURIComponent(itemId)}/source`, "_blank", "noopener");
    },

    async openForageCardSummary(row) {
      const path = String(row?.summary_path || "").trim();
      if (!path) {
        window.alert("No summary file available for this research card.");
        return;
      }
      if (row._expanded) {
        row._expanded = false;
        return;
      }
      try {
        if (!row._content_markdown) {
          const payload = await this.apiGet(`/api/markdown?path=${encodeURIComponent(path)}`);
          row._content_markdown = markdownToHtml(String(payload.content || "").trim());
        }
        row._expanded = true;
      } catch (err) {
        window.alert("Could not load summary: " + String(err.message || err));
      }
    },

    async toggleForageCardPin(row) {
      const cardId = String(row?.id || "").trim();
      if (!cardId) return;
      try {
        const result = await this.apiPost(`/api/forage-cards/${encodeURIComponent(cardId)}/pin`, {});
        if (result?.card) {
          const idx = (this.panelData || []).findIndex((r) => r.id === cardId);
          if (idx >= 0) this.panelData[idx] = { ...result.card };
        } else {
          await this.refreshSystemPanel();
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert("Pin failed: " + String(err.message || err));
      }
    },

    async deleteForageCard(row) {
      const cardId = String(row?.id || "").trim();
      if (!cardId) return;
      if (!window.confirm("Delete this research card?")) return;
      try {
        await this.apiDelete(`/api/forage-cards/${encodeURIComponent(cardId)}`);
        this.panelData = (this.panelData || []).filter((r) => r.id !== cardId);
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert("Delete failed: " + String(err.message || err));
      }
    },

    async cancelForagingJob(row) {
      const requestId = String(row?.id || "").trim();
      const conversationId = String(row?.conversation_id || "").trim();
      if (!requestId || !conversationId) {
        return;
      }
      const confirmed = window.confirm(`Cancel Research job ${requestId}?`);
      if (!confirmed) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/jobs/${encodeURIComponent(requestId)}/cancel`, {
          conversation_id: conversationId,
        });
        window.alert(payload.message || "Cancel requested.");
      } catch (err) {
        window.alert(`Cancel failed: ${String(err.message || err)}`);
      } finally {
        try {
          await this.refreshSystemPanel();
          await this.refreshPanelBadges();
        } catch (_err) {}
      }
    },

    async cancelBuildingJob(row) {
      const requestId = String(row?.id || "").trim();
      const conversationId = String(row?.conversation_id || "").trim();
      if (!requestId || !conversationId) {
        return;
      }
      const confirmed = window.confirm(`Cancel Build job ${requestId}?`);
      if (!confirmed) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/jobs/${encodeURIComponent(requestId)}/cancel`, {
          conversation_id: conversationId,
        });
        window.alert(payload.message || "Cancel requested.");
      } catch (err) {
        window.alert(`Cancel failed: ${String(err.message || err)}`);
      } finally {
        try {
          await this.refreshSystemPanel();
          await this.refreshPanelBadges();
        } catch (_err) {}
      }
    },

    async ingestOutbox(row) {
      const threadId = String(row?.id || "").trim();
      const target = String(row?.target || "").trim();
      if (!threadId || !target) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/outbox/${encodeURIComponent(target)}/${encodeURIComponent(threadId)}/ingest`, {
          lane: "project",
        });
        window.alert(payload.message || "Codex outbox item ingested.");
      } catch (err) {
        window.alert(`Codex outbox ingest failed: ${String(err.message || err)}`);
      } finally {
        try {
          await this.refreshSystemPanel();
          await this.refreshPanelBadges();
        } catch (_err) {}
      }
    },
    async fetchAuthStatus() {
      const response = await fetch("/api/auth/status", { method: "GET" });
      if (!response.ok) {
        throw new Error(`Auth status failed (${response.status})`);
      }
      const payload = await response.json();
      this.auth.enabled = Boolean(payload.enabled);
      this.auth.authenticated = Boolean(payload.authenticated);
      this.auth.profile = payload.profile && typeof payload.profile === "object" ? payload.profile : null;
      this.authSetup.required = Boolean(payload.setup_required);
      this.authSetup.allowed = payload.setup_allowed !== false;
      this.authSetup.message = String(payload.setup_message || "").trim();
      if (!this.authSetup.username) {
        this.authSetup.username = String(payload.default_owner_username || "owner").trim().toLowerCase() || "owner";
      }
      if (this.auth.authenticated && this.auth.profile) {
        this.loginUsername = String(this.auth.profile.username || this.loginUsername || "").trim();
        this.authShowForm = false;
        this.authSetup.required = false;
        this.authSetup.message = "";
        this.loadLessonReadState();
        this.loadReflectionReadState();
        this.refreshHomePhrase();
        this._updateHomeClock();
      }
      if (this.authSetup.required) {
        if (!this.authSetup.username) {
          this.authSetup.username = String(this.loginUsername || "owner").trim().toLowerCase() || "owner";
        }
        this.authShowForm = false;
        this.loginPassword = "";
      }
      if (!this.auth.authenticated && !this.loginUsername) {
        this.loginUsername = "owner";
      }
      if (!this.auth.authenticated) {
        this.authShowForm = false;
        this.lessonsReadIds = {};
        this.lessonsUnreadCount = 0;
        this.reflectionsReadIds = {};
        this.reflectionsUnreadCount = 0;
        this.refreshHomePhrase();
        this._updateHomeClock();
      }
      await this.refreshWebPushSettings();
    },

    beginCheckIn() {
      if (this.authSetup.required) {
        return;
      }
      this.authError = "";
      this.authShowForm = true;
      this.$nextTick(() => {
        const field = this.$refs.loginUsernameInput;
        if (field && typeof field.focus === "function") {
          field.focus();
        }
      });
    },

    cancelCheckIn() {
      this.authError = "";
      this.loginPassword = "";
      this.authShowForm = false;
    },

    async finalizeAuthSuccess(payload) {
      this.auth.enabled = Boolean(payload.enabled);
      this.auth.authenticated = Boolean(payload.authenticated);
      this.auth.profile = payload.profile && typeof payload.profile === "object" ? payload.profile : null;
      if (!this.auth.profile) {
        throw new Error("No profile returned from server.");
      }
      this.loginUsername = String(this.auth.profile.username || this.loginUsername || "").trim();
      this.authSetup.required = false;
      this.authSetup.allowed = false;
      this.authSetup.message = "";
      this.authSetup.password = "";
      this.authSetup.confirmPassword = "";
      this.loadLessonReadState();
      this.loadReflectionReadState();
      await this.refreshWebPushSettings();
      try {
        localStorage.setItem("oathweaver_login_username", this.loginUsername);
      } catch (_err) {}
      this.loginPassword = "";
      this.authShowForm = false;
      this.waypointDayPanelExpanded = true;
      this.refreshHomePhrase();
      this._updateHomeClock();
      await this.bootstrapConversations({ activateApp: false });
      try {
        await this.refreshWaypointState();
      } catch (_err) {}
      await this.refreshPanelBadges();
      this.setActiveApp("home");
    },

    async submitOwnerSetup() {
      this.authError = "";
      const username = String(this.authSetup.username || "").trim().toLowerCase();
      const password = String(this.authSetup.password || "");
      const confirmPassword = String(this.authSetup.confirmPassword || "");
      if (!username) {
        this.authError = "Username is required.";
        return;
      }
      if (!password) {
        this.authError = "Password is required.";
        return;
      }
      if (password !== confirmPassword) {
        this.authError = "Password confirmation does not match.";
        return;
      }
      this.authSetup.submitting = true;
      try {
        const payload = await this.apiPost("/api/auth/setup-owner", {
          username,
          password,
          confirm_password: confirmPassword,
        });
        await this.finalizeAuthSuccess(payload);
      } catch (err) {
        this.authError = String(err.message || err);
      } finally {
        this.authSetup.submitting = false;
      }
    },

    async submitLogin() {
      if (this.authSetup.required) {
        this.authError = "Create the owner account first.";
        return;
      }
      this.authError = "";
      const username = String(this.loginUsername || "").trim();
      if (!username) {
        this.authError = "Username is required.";
        this.authShowForm = true;
        return;
      }
      try {
        const payload = await this.apiPost("/api/auth/login", {
          username,
          password: this.loginPassword,
        });
        await this.finalizeAuthSuccess(payload);
      } catch (err) {
        this.authError = String(err.message || err);
        this.authShowForm = true;
      }
    },

    async refreshConversations(options = {}) {
      const payload = await this.apiGet("/api/conversations");
      this.conversations = Array.isArray(payload.conversations) ? payload.conversations : [];
      if (options?.refreshSidebarLane !== false) {
        this.ensureSidebarProjectLaneFresh().catch(() => {});
      }
      if (options?.skipAutoRead === true) {
        return;
      }
      const activeId = String(this.activeConversationId || "").trim();
      if (String(this.activeApp || "").trim() !== "chat" || !activeId) {
        return;
      }
      const activeRow = this.conversations.find((row) => String(row?.id || "").trim() === activeId);
      if (Number(activeRow?.unread_count || 0) <= 0) {
        return;
      }
      const marked = await this.markConversationRead(activeId, { refreshList: false });
      if (!marked) {
        return;
      }
      this.conversations = this.conversations.map((row) => {
        if (String(row?.id || "").trim() !== activeId) {
          return row;
        }
        return {
          ...row,
          unread_count: 0,
          has_unread: false,
        };
      });
    },

    async openConversation(id, options = {}) {
      const targetId = String(id || "").trim();
      if (!targetId) {
        return;
      }
      const previousId = String(this.activeConversationId || "").trim();
      if (previousId) {
        this.saveDraftForConversation(previousId);
        this.saveComposerStateForConversation(previousId);
      }
      const payload = await this.apiGet(`/api/conversations/${encodeURIComponent(targetId)}`);
      const convo = payload.conversation || null;
      if (!convo) {
        return;
      }
      this.activeConversationId = convo.id;
      this.activeConversation = convo;
      this.syncImagePrefsFromConversation(convo);
      this.setActiveProject(convo.project || this.activeProject);
      this.activeTopicId = normalizeTopicId(convo.topic_id || (String(convo.project || "").trim() === "general" ? "general" : this.activeTopicId));
      this.chatMenuOpen = false;
      this.composerAddMenuOpen = false;
      this.actionsOverlayOpen = false;
      this.panelOverlayOpen = false;
      this.restoreDraftForConversation(convo.id);
      this.restoreComposerStateForConversation(convo.id);
      const activateApp = options?.activateApp !== false;
      if (activateApp) {
        this.setActiveApp("chat");
      }
      if (activateApp && this.isMobileLayout()) {
        this.closeSidebar();
      }
      location.hash = `#${convo.id}`;
      this.$nextTick(() => {
        this.resizeComposer();
        if (activateApp) {
          this.scrollMessages();
        }
      });
      this.markConversationRead(convo.id, { refreshList: true });
    },

    async createConversation(kind = "", options = {}) {
      if (this.auth.enabled && !this.auth.authenticated) {
        return;
      }
      const request = { kind: kind || "" };
      if (Object.prototype.hasOwnProperty.call(options || {}, "topicId")) {
        request.topic_id = normalizeTopicId(options.topicId);
      }
      if (Object.prototype.hasOwnProperty.call(options || {}, "project")) {
        request.project = normalizeProjectSlug(options.project);
      } else if (String(kind || "").trim().toLowerCase() === "general") {
        request.project = "general";
        request.topic_id = "general";
      } else if (options && options.useActiveProject === true) {
        request.project = normalizeProjectSlug(this.activeProject);
      }
      const payload = await this.apiPost("/api/conversations", request);
      const convo = payload.conversation || null;
      if (!convo) {
        return;
      }
      await this.refreshConversations();
      await this.ensureSidebarProjectLaneFresh({ force: true });
      await this.openConversation(convo.id, options);
    },

    async deleteConversation(id) {
      const conversationId = String(id || "").trim();
      if (!conversationId) {
        return;
      }
      const confirmed = window.confirm("Delete this project?");
      if (!confirmed) {
        return;
      }
      await this.apiDelete(`/api/conversations/${encodeURIComponent(conversationId)}`);
      this.clearDraftForConversation(conversationId);
      this.clearComposerStateForConversation(conversationId, { releaseAssets: true });
      if (this.activeConversationId === conversationId) {
        this.activeConversationId = null;
        this.activeConversation = null;
      }
      await this.refreshConversations();
      await this.ensureSidebarProjectLaneFresh({ force: true });
      if (!this.activeConversationId && this.conversations.length > 0) {
        await this.openConversation(this.conversations[0].id);
      }
    },

    async renameConversation() {
      this.chatMenuOpen = false;
      if (!this.activeConversationId) {
        return;
      }
      const currentTitle = String(this.activeConversation?.title || "New Thread");
      const value = window.prompt("Rename this conversation:", currentTitle);
      if (!value || !value.trim()) {
        return;
      }
      const payload = await this.apiPatch(`/api/conversations/${encodeURIComponent(this.activeConversationId)}`, {
        title: value.trim(),
      });
      if (payload.conversation) {
        this.activeConversation = payload.conversation;
      }
      await this.refreshConversations();
    },

    async fetchProjectNames() {
      const payload = await this.apiGet("/api/projects?limit=200");
      const names = Array.isArray(payload.projects) ? payload.projects : [];
      const cleaned = names.map((x) => normalizeProjectSlug(x)).filter((x) => Boolean(x));
      if (!cleaned.includes("general")) {
        cleaned.unshift("general");
      }
      return Array.from(new Set(cleaned));
    },

    async refreshProjectPickerRows() {
      this.projectPickerLoading = true;
      this.projectPickerError = "";
      try {
        const payload = await this.apiGet("/api/panel/projects?limit=200");
        const rows = Array.isArray(payload.projects) ? payload.projects : [];
        this.projectPickerRows = rows
          .map((row) => ({
            project: normalizeProjectSlug(row?.project || ""),
            description: String(row?.description || "").trim(),
            updated_at: String(row?.updated_at || "").trim(),
            source: String(row?.source || "").trim(),
          }))
          .filter((row) => Boolean(row.project));
      } catch (err) {
        this.projectPickerRows = [];
        this.projectPickerError = String(err.message || err);
      } finally {
        this.projectPickerLoading = false;
      }
    },

    openProjectPickerModal() {
      this.chatMenuOpen = false;
      this.projectPickerSearch = "";
      this.projectPickerError = "";
      this.projectPickerSubmitting = false;
      this.projectPickerForm = {
        project: normalizeProjectSlug(this.activeProject || "general"),
        description: "",
      };
      const current = (this.projectPickerRows || []).find(
        (row) => String(row?.project || "").trim() === this.projectPickerForm.project
      );
      if (current) {
        this.projectPickerForm.description = String(current.description || "").trim();
      }
      this.projectPickerOpen = true;
      this.updateBodyClasses();
      this.refreshProjectPickerRows().then(() => {
        const latest = (this.projectPickerRows || []).find(
          (row) => String(row?.project || "").trim() === this.projectPickerForm.project
        );
        if (latest) {
          this.projectPickerForm.description = String(latest.description || "").trim();
        }
      });
      this.$nextTick(() => {
        const node = this.$refs.projectPickerNameInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    closeProjectPickerModal() {
      this.projectPickerOpen = false;
      this.projectPickerLoading = false;
      this.projectPickerSubmitting = false;
      this.projectPickerError = "";
      this.updateBodyClasses();
    },

    defaultProjectBranchSlug() {
      const sourceProject = normalizeProjectSlug(this.activeConversation?.project || this.activeProject || "project");
      const titleSlug = normalizeProjectSlug(this.activeConversation?.title || "branch");
      let candidate = normalizeProjectSlug(`${sourceProject}_${titleSlug || "branch"}`);
      if (!candidate || candidate === "general" || candidate === sourceProject) {
        candidate = normalizeProjectSlug(`${sourceProject}_branch`);
      }
      const existing = new Set(
        (this.projectPickerRows || []).map((row) => normalizeProjectSlug(row?.project || "")).filter((x) => Boolean(x))
      );
      if (!existing.has(candidate)) {
        return candidate;
      }
      for (let idx = 2; idx <= 99; idx += 1) {
        const nextCandidate = normalizeProjectSlug(`${candidate}_${idx}`);
        if (!existing.has(nextCandidate)) {
          return nextCandidate;
        }
      }
      return normalizeProjectSlug(`${candidate}_${Date.now().toString().slice(-5)}`);
    },

    openProjectBranchModal() {
      this.chatMenuOpen = false;
      if (!this.activeConversationId) {
        window.alert("Open a branch first.");
        return;
      }
      const sourceProject = normalizeProjectSlug(this.activeConversation?.project || this.activeProject || "general");
      const sourceRow = (this.projectPickerRows || []).find(
        (row) => normalizeProjectSlug(row?.project || "") === sourceProject
      );
      this.projectBranchSearch = "";
      this.projectBranchError = "";
      this.projectBranchSubmitting = false;
      this.projectBranchForm = {
        project: this.defaultProjectBranchSlug(),
        description: String(sourceRow?.description || "").trim(),
        mode: "clone",
        copy_project_data: false,
      };
      this.projectBranchModalOpen = true;
      this.updateBodyClasses();
      this.refreshProjectPickerRows().catch(() => {});
      this.$nextTick(() => {
        const node = this.$refs.projectBranchNameInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    closeProjectBranchModal() {
      this.projectBranchModalOpen = false;
      this.projectBranchSubmitting = false;
      this.projectBranchError = "";
      this.updateBodyClasses();
    },

    selectProjectBranchRow(row) {
      const slug = normalizeProjectSlug(row?.project || "");
      if (!slug) {
        return;
      }
      this.projectBranchForm.project = slug;
      this.projectBranchForm.description = String(row?.description || "").trim();
    },

    normalizeProjectBranchProject() {
      this.projectBranchForm.project = normalizeProjectSlug(this.projectBranchForm.project || "");
    },

    async submitProjectBranchPromotion() {
      try {
        this.projectBranchSubmitting = true;
        this.normalizeProjectBranchProject();
        const targetProject = normalizeProjectSlug(this.projectBranchForm.project || "");
        if (!targetProject || targetProject === "general") {
          window.alert("Choose a non-general target project.");
          return;
        }
        if (!this.activeConversationId) {
          window.alert("Open a branch first.");
          return;
        }
        const payload = await this.apiPost("/api/projects/promote-branch", {
          source_conversation_id: this.activeConversationId,
          target_project: targetProject,
          mode: String(this.projectBranchForm.mode || "clone").trim().toLowerCase(),
          copy_project_data: Boolean(this.projectBranchForm.copy_project_data),
          description: String(this.projectBranchForm.description || "").trim(),
        });
        const conversationId = String(payload?.conversation?.id || this.activeConversationId || "").trim();
        this.closeProjectBranchModal();
        await this.refreshConversations();
        await this.refreshPanelBadges();
        await this.ensureSidebarProjectLaneFresh({ force: true });
        if (conversationId) {
          await this.openConversation(conversationId, { activateApp: true });
        }
      } catch (err) {
        this.projectBranchError = String(err.message || err);
      } finally {
        this.projectBranchSubmitting = false;
      }
    },

    selectProjectPickerRow(row) {
      const slug = normalizeProjectSlug(row?.project || "");
      if (!slug) {
        return;
      }
      this.projectPickerForm.project = slug;
      this.projectPickerForm.description = String(row?.description || "").trim();
    },

    normalizeProjectPickerProject() {
      this.projectPickerForm.project = normalizeProjectSlug(this.projectPickerForm.project || "general");
    },

    async saveProjectPickerCatalog() {
      const slug = normalizeProjectSlug(this.projectPickerForm.project || "");
      if (!slug) {
        window.alert("Project name is required.");
        return null;
      }
      const payload = await this.apiPost("/api/projects/catalog", {
        project: slug,
        description: String(this.projectPickerForm.description || "").trim(),
      });
      await this.refreshProjectPickerRows();
      await this.ensureSidebarProjectLaneFresh({ force: true });
      const latest = (this.projectPickerRows || []).find((row) => String(row?.project || "").trim() === slug);
      if (latest) {
        this.projectPickerForm.description = String(latest.description || "").trim();
      }
      return payload;
    },

    async submitProjectPickerCreate() {
      try {
        this.projectPickerSubmitting = true;
        this.normalizeProjectPickerProject();
        await this.saveProjectPickerCatalog();
        await this.setConversationProjectSlug(this.projectPickerForm.project);
        this.closeProjectPickerModal();
      } catch (err) {
        this.projectPickerError = String(err.message || err);
      } finally {
        this.projectPickerSubmitting = false;
      }
    },

    async submitProjectPickerUse() {
      try {
        this.projectPickerSubmitting = true;
        this.normalizeProjectPickerProject();
        if (!String(this.projectPickerForm.project || "").trim()) {
          window.alert("Choose or enter a project.");
          return;
        }
        await this.setConversationProjectSlug(this.projectPickerForm.project);
        this.closeProjectPickerModal();
      } catch (err) {
        this.projectPickerError = String(err.message || err);
      } finally {
        this.projectPickerSubmitting = false;
      }
    },

    async setConversationProjectSlug(project) {
      const slug = normalizeProjectSlug(project);
      if (!this.activeConversationId) {
        this.setActiveProject(slug);
        await this.ensureSidebarProjectLaneFresh({ force: true });
        return slug;
      }
      const payload = await this.apiPatch(`/api/conversations/${encodeURIComponent(this.activeConversationId)}`, {
        project: slug,
      });
      if (payload.conversation) {
        this.activeConversation = payload.conversation;
        this.activeConversationId = payload.conversation.id || this.activeConversationId;
        this.activeTopicId = normalizeTopicId(payload.conversation.topic_id || this.activeTopicId);
      }
      this.setActiveProject(slug);
      await this.refreshConversations();
      await this.refreshPanelBadges();
      await this.ensureSidebarProjectLaneFresh({ force: true });
      return slug;
    },

    async setConversationTopic(topicId, projectSlug = "") {
      const normalizedTopicId = normalizeTopicId(topicId);
      const slug = normalizeProjectSlug(projectSlug || this.activeProject || "general");
      if (!this.activeConversationId) {
        this.activeTopicId = normalizedTopicId;
        this.setActiveProject(slug);
        await this.ensureSidebarProjectLaneFresh({ force: true });
        return normalizedTopicId;
      }
      const payload = await this.apiPatch(`/api/conversations/${encodeURIComponent(this.activeConversationId)}`, {
        project: slug,
        topic_id: normalizedTopicId,
      });
      if (payload.conversation) {
        this.activeConversation = payload.conversation;
        this.activeConversationId = payload.conversation.id || this.activeConversationId;
      }
      this.activeTopicId = normalizedTopicId;
      this.setActiveProject(slug);
      await this.refreshConversations();
      await this.refreshPanelBadges();
      await this.ensureSidebarProjectLaneFresh({ force: true });
      return normalizedTopicId;
    },

    async setProject() {
      this.openProjectPickerModal();
    },

    async usePanelProject(project) {
      if (!project) {
        return;
      }
      try {
        await this.setConversationProjectSlug(project);
        await this.openSystemPanel("project_detail");
      } catch (err) {
        window.alert(`Project switch failed: ${String(err.message || err)}`);
      }
    },

    async openAgentGraphModal() {
      this.chatMenuOpen = false;
      this.agentGraphError = "";
      this.agentGraphModalOpen = true;
      this.updateBodyClasses();
      if (!Array.isArray(this.agentGraphData?.nodes) || !this.agentGraphData.nodes.length) {
        this.resetAgentGraphView();
      }
      await this.refreshAgentGraph();
    },

    closeAgentGraphModal() {
      this.agentGraphModalOpen = false;
      this.agentGraphDragState = null;
      this.agentGraphPanState = null;
      this.agentGraphActivePointers = {};
      this.agentGraphPinchState = null;
      this.updateBodyClasses();
    },

    agentGraphNodeSize(node) {
      const kind = String(node?.kind || "").trim().toLowerCase();
      if (kind === "root") return { width: 250, height: 86 };
      if (kind === "lane") return { width: 230, height: 76 };
      if (kind === "job") return { width: 280, height: 82 };
      return { width: 260, height: 74 };
    },

    agentGraphMetaRows(node) {
      const meta = node && typeof node === "object" ? node.meta : {};
      if (!meta || typeof meta !== "object") {
        return [];
      }
      return Object.keys(meta)
        .sort((a, b) => a.localeCompare(b))
        .map((key) => {
          const value = meta[key];
          if (value === null || value === undefined) {
            return null;
          }
          let text = "";
          if (Array.isArray(value)) {
            text = value.join(", ");
          } else if (typeof value === "object") {
            try {
              text = JSON.stringify(value);
            } catch (_err) {
              text = String(value);
            }
          } else {
            text = String(value);
          }
          text = text.trim();
          if (!text) {
            return null;
          }
          return {
            key: key.replace(/_/g, " "),
            value: text.length > 180 ? `${text.slice(0, 177)}...` : text,
          };
        })
        .filter(Boolean);
    },

    selectAgentGraphNode(nodeId) {
      const id = String(nodeId || "").trim();
      this.agentGraphSelectedNodeId = id;
    },

    resetAgentGraphView() {
      this.agentGraphZoom = 1;
      this.agentGraphPan = { x: 28, y: 20 };
    },

    zoomAgentGraphBy(factor, anchorCanvas = null) {
      const oldZoom = Number(this.agentGraphZoom || 1);
      const safeOldZoom = Number.isFinite(oldZoom) && oldZoom > 0 ? oldZoom : 1;
      const nextZoom = Math.max(
        AGENT_GRAPH_MIN_ZOOM,
        Math.min(AGENT_GRAPH_MAX_ZOOM, safeOldZoom * Number(factor || 1))
      );
      if (Math.abs(nextZoom - safeOldZoom) < 0.0001) {
        return;
      }
      const anchor = anchorCanvas && Number.isFinite(anchorCanvas.x) && Number.isFinite(anchorCanvas.y)
        ? anchorCanvas
        : { x: AGENT_GRAPH_VIEW_WIDTH / 2, y: AGENT_GRAPH_VIEW_HEIGHT / 2 };
      const panX = Number(this.agentGraphPan?.x || 0);
      const panY = Number(this.agentGraphPan?.y || 0);
      const worldX = (anchor.x - panX) / safeOldZoom;
      const worldY = (anchor.y - panY) / safeOldZoom;
      this.agentGraphZoom = nextZoom;
      this.agentGraphPan = {
        x: anchor.x - worldX * nextZoom,
        y: anchor.y - worldY * nextZoom,
      };
    },

    zoomAgentGraphIn() {
      this.zoomAgentGraphBy(1.12);
    },

    zoomAgentGraphOut() {
      this.zoomAgentGraphBy(1 / 1.12);
    },

    agentGraphClientToCanvas(event) {
      const svg = this.$refs.agentGraphCanvas;
      if (!svg || typeof svg.getBoundingClientRect !== "function") {
        return null;
      }
      const rect = svg.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return null;
      }
      const x = ((Number(event?.clientX || 0) - rect.left) / rect.width) * AGENT_GRAPH_VIEW_WIDTH;
      const y = ((Number(event?.clientY || 0) - rect.top) / rect.height) * AGENT_GRAPH_VIEW_HEIGHT;
      return { x, y };
    },

    agentGraphClientToWorld(event) {
      const canvasPoint = this.agentGraphClientToCanvas(event);
      if (!canvasPoint) {
        return null;
      }
      const zoom = Number(this.agentGraphZoom || 1);
      const safeZoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
      const panX = Number(this.agentGraphPan?.x || 0);
      const panY = Number(this.agentGraphPan?.y || 0);
      return {
        x: (canvasPoint.x - panX) / safeZoom,
        y: (canvasPoint.y - panY) / safeZoom,
      };
    },

    agentGraphPointerId(event) {
      const pointerId = Number(event?.pointerId);
      return Number.isFinite(pointerId) ? pointerId : null;
    },

    agentGraphAcceptsPrimaryPointer(event) {
      const pointerType = String(event?.pointerType || "mouse").trim().toLowerCase();
      if (pointerType === "mouse") {
        return Number(event?.button) === 0;
      }
      return true;
    },

    agentGraphPointerEntries() {
      const pointers = this.agentGraphActivePointers && typeof this.agentGraphActivePointers === "object"
        ? this.agentGraphActivePointers
        : {};
      return Object.entries(pointers)
        .map(([pointerIdRaw, point]) => {
          const pointerId = Number(pointerIdRaw);
          const x = Number(point?.x);
          const y = Number(point?.y);
          if (!Number.isFinite(pointerId) || !Number.isFinite(x) || !Number.isFinite(y)) {
            return null;
          }
          return {
            pointerId,
            point: { x, y },
          };
        })
        .filter(Boolean);
    },

    trackAgentGraphPointer(event) {
      const pointerId = this.agentGraphPointerId(event);
      const point = this.agentGraphClientToCanvas(event);
      if (pointerId === null || !point) {
        return null;
      }
      this.agentGraphActivePointers = {
        ...(this.agentGraphActivePointers || {}),
        [pointerId]: point,
      };
      return { pointerId, point };
    },

    untrackAgentGraphPointer(pointerId) {
      if (pointerId === null) {
        return;
      }
      const pointers = this.agentGraphActivePointers && typeof this.agentGraphActivePointers === "object"
        ? this.agentGraphActivePointers
        : {};
      if (!Object.prototype.hasOwnProperty.call(pointers, pointerId)) {
        return;
      }
      const next = { ...pointers };
      delete next[pointerId];
      this.agentGraphActivePointers = next;
    },

    startAgentGraphPinchFromTrackedPointers() {
      const pointers = this.agentGraphPointerEntries();
      if (pointers.length < 2) {
        this.agentGraphPinchState = null;
        return false;
      }
      const first = pointers[0];
      const second = pointers[1];
      const startDistanceRaw = Math.hypot(
        Number(second.point.x || 0) - Number(first.point.x || 0),
        Number(second.point.y || 0) - Number(first.point.y || 0)
      );
      const startDistance = Number.isFinite(startDistanceRaw) && startDistanceRaw > 0 ? startDistanceRaw : 1;
      const startZoomRaw = Number(this.agentGraphZoom || 1);
      const startZoom = Number.isFinite(startZoomRaw) && startZoomRaw > 0 ? startZoomRaw : 1;
      this.agentGraphPinchState = {
        pointerIdA: first.pointerId,
        pointerIdB: second.pointerId,
        startDistance,
        startCenter: {
          x: (Number(first.point.x || 0) + Number(second.point.x || 0)) / 2,
          y: (Number(first.point.y || 0) + Number(second.point.y || 0)) / 2,
        },
        startZoom,
        startPanX: Number(this.agentGraphPan?.x || 0),
        startPanY: Number(this.agentGraphPan?.y || 0),
      };
      this.agentGraphPanState = null;
      this.agentGraphDragState = null;
      return true;
    },

    onAgentGraphCanvasWheel(event) {
      if (!this.agentGraphModalOpen) {
        return;
      }
      const anchor = this.agentGraphClientToCanvas(event);
      const factor = Number(event?.deltaY || 0) < 0 ? 1.09 : 1 / 1.09;
      this.zoomAgentGraphBy(factor, anchor);
    },

    onAgentGraphCanvasMouseDown(event) {
      if (!this.agentGraphModalOpen) {
        return;
      }
      if (!this.agentGraphAcceptsPrimaryPointer(event)) {
        return;
      }
      const tracked = this.trackAgentGraphPointer(event);
      const pointerId = tracked ? tracked.pointerId : this.agentGraphPointerId(event);
      if (
        pointerId !== null &&
        event?.currentTarget &&
        typeof event.currentTarget.setPointerCapture === "function"
      ) {
        try {
          event.currentTarget.setPointerCapture(pointerId);
        } catch (_err) {}
      }
      const pointerCount = this.agentGraphPointerEntries().length;
      if (pointerCount >= 2) {
        this.startAgentGraphPinchFromTrackedPointers();
        if (event?.cancelable) {
          event.preventDefault();
        }
        return;
      }
      const point = tracked ? tracked.point : this.agentGraphClientToCanvas(event);
      if (!point) {
        return;
      }
      this.agentGraphPinchState = null;
      this.agentGraphPanState = {
        pointerId,
        startX: point.x,
        startY: point.y,
        panX: Number(this.agentGraphPan?.x || 0),
        panY: Number(this.agentGraphPan?.y || 0),
      };
      if (event?.cancelable) {
        event.preventDefault();
      }
    },

    startAgentGraphNodeDrag(event, nodeId) {
      if (!this.agentGraphModalOpen) {
        return;
      }
      if (!this.agentGraphAcceptsPrimaryPointer(event)) {
        return;
      }
      const id = String(nodeId || "").trim();
      if (!id) {
        return;
      }
      const worldPoint = this.agentGraphClientToWorld(event);
      const node = this.agentGraphNodes.find((item) => String(item?.id || "").trim() === id);
      if (!node || !worldPoint) {
        return;
      }
      const tracked = this.trackAgentGraphPointer(event);
      const pointerId = tracked ? tracked.pointerId : this.agentGraphPointerId(event);
      if (
        pointerId !== null &&
        event?.currentTarget &&
        typeof event.currentTarget.setPointerCapture === "function"
      ) {
        try {
          event.currentTarget.setPointerCapture(pointerId);
        } catch (_err) {}
      }
      if (this.agentGraphPointerEntries().length >= 2) {
        this.startAgentGraphPinchFromTrackedPointers();
        if (event?.cancelable) {
          event.preventDefault();
        }
        return;
      }
      this.agentGraphPinchState = null;
      this.agentGraphDragState = {
        nodeId: id,
        pointerId,
        offsetX: worldPoint.x - Number(node.x || 0),
        offsetY: worldPoint.y - Number(node.y || 0),
      };
      this.agentGraphPanState = null;
      this.agentGraphSelectedNodeId = id;
      if (event?.cancelable) {
        event.preventDefault();
      }
    },

    onAgentGraphCanvasMouseMove(event) {
      const pointerId = this.agentGraphPointerId(event);
      if (pointerId !== null) {
        this.trackAgentGraphPointer(event);
      }
      const pinch = this.agentGraphPinchState;
      if (pinch) {
        const pointers = this.agentGraphActivePointers && typeof this.agentGraphActivePointers === "object"
          ? this.agentGraphActivePointers
          : {};
        const pointA = pointers[pinch.pointerIdA];
        const pointB = pointers[pinch.pointerIdB];
        if (pointA && pointB) {
          const currentDistanceRaw = Math.hypot(
            Number(pointB.x || 0) - Number(pointA.x || 0),
            Number(pointB.y || 0) - Number(pointA.y || 0)
          );
          const currentDistance = Number.isFinite(currentDistanceRaw) && currentDistanceRaw > 0
            ? currentDistanceRaw
            : Number(pinch.startDistance || 1);
          const scale = currentDistance / Math.max(1, Number(pinch.startDistance || 1));
          const safeStartZoom = Number.isFinite(Number(pinch.startZoom)) && Number(pinch.startZoom) > 0
            ? Number(pinch.startZoom)
            : 1;
          const nextZoom = Math.max(
            AGENT_GRAPH_MIN_ZOOM,
            Math.min(AGENT_GRAPH_MAX_ZOOM, safeStartZoom * scale)
          );
          const center = {
            x: (Number(pointA.x || 0) + Number(pointB.x || 0)) / 2,
            y: (Number(pointA.y || 0) + Number(pointB.y || 0)) / 2,
          };
          const worldX = (Number(pinch.startCenter?.x || 0) - Number(pinch.startPanX || 0)) / safeStartZoom;
          const worldY = (Number(pinch.startCenter?.y || 0) - Number(pinch.startPanY || 0)) / safeStartZoom;
          this.agentGraphZoom = nextZoom;
          this.agentGraphPan = {
            x: center.x - worldX * nextZoom,
            y: center.y - worldY * nextZoom,
          };
          if (event?.cancelable) {
            event.preventDefault();
          }
          return;
        }
        this.agentGraphPinchState = null;
      }
      if (this.agentGraphPointerEntries().length >= 2) {
        this.startAgentGraphPinchFromTrackedPointers();
        if (event?.cancelable) {
          event.preventDefault();
        }
        return;
      }
      const drag = this.agentGraphDragState;
      if (drag && drag.nodeId) {
        if (drag.pointerId !== null && pointerId !== null && drag.pointerId !== pointerId) {
          return;
        }
        const worldPoint = this.agentGraphClientToWorld(event);
        if (!worldPoint) {
          return;
        }
        const nextX = Math.max(60, Math.min(AGENT_GRAPH_VIEW_WIDTH - 60, worldPoint.x - Number(drag.offsetX || 0)));
        const nextY = Math.max(40, Math.min(AGENT_GRAPH_VIEW_HEIGHT - 40, worldPoint.y - Number(drag.offsetY || 0)));
        this.agentGraphPositions = {
          ...(this.agentGraphPositions || {}),
          [drag.nodeId]: { x: nextX, y: nextY },
        };
        if (event?.cancelable) {
          event.preventDefault();
        }
        return;
      }
      const pan = this.agentGraphPanState;
      if (!pan) {
        return;
      }
      if (pan.pointerId !== null && pointerId !== null && pan.pointerId !== pointerId) {
        return;
      }
      const point = pointerId !== null
        ? (this.agentGraphActivePointers && this.agentGraphActivePointers[pointerId]) || this.agentGraphClientToCanvas(event)
        : this.agentGraphClientToCanvas(event);
      if (!point) {
        return;
      }
      this.agentGraphPan = {
        x: Number(pan.panX || 0) + (point.x - Number(pan.startX || 0)),
        y: Number(pan.panY || 0) + (point.y - Number(pan.startY || 0)),
      };
      if (event?.cancelable) {
        event.preventDefault();
      }
    },

    onAgentGraphCanvasMouseUp(event = null) {
      const pointerId = this.agentGraphPointerId(event);
      if (
        pointerId !== null &&
        event?.currentTarget &&
        typeof event.currentTarget.releasePointerCapture === "function"
      ) {
        try {
          event.currentTarget.releasePointerCapture(pointerId);
        } catch (_err) {}
      }
      this.untrackAgentGraphPointer(pointerId);
      const drag = this.agentGraphDragState;
      if (drag && (pointerId === null || Number(drag.pointerId) === pointerId)) {
        this.agentGraphDragState = null;
      }
      const pan = this.agentGraphPanState;
      if (pan && (pointerId === null || Number(pan.pointerId) === pointerId)) {
        this.agentGraphPanState = null;
      }
      const pinch = this.agentGraphPinchState;
      if (
        pinch &&
        (
          pointerId === null ||
          Number(pinch.pointerIdA) === pointerId ||
          Number(pinch.pointerIdB) === pointerId
        )
      ) {
        this.agentGraphPinchState = null;
      }
      const remaining = this.agentGraphPointerEntries();
      if (remaining.length >= 2) {
        this.startAgentGraphPinchFromTrackedPointers();
        return;
      }
      if (remaining.length === 1 && !this.agentGraphDragState) {
        const lone = remaining[0];
        this.agentGraphPanState = {
          pointerId: lone.pointerId,
          startX: Number(lone.point.x || 0),
          startY: Number(lone.point.y || 0),
          panX: Number(this.agentGraphPan?.x || 0),
          panY: Number(this.agentGraphPan?.y || 0),
        };
      }
    },

    seedAgentGraphLayout() {
      const rows = Array.isArray(this.agentGraphData?.nodes) ? this.agentGraphData.nodes : [];
      const previous = this.agentGraphPositions && typeof this.agentGraphPositions === "object"
        ? this.agentGraphPositions
        : {};
      const columns = [
        { kind: "root", x: 180 },
        { kind: "lane", x: 450 },
        { kind: "job", x: 810 },
        { kind: "agent", x: 1180 },
      ];
      const grouped = {
        root: [],
        lane: [],
        job: [],
        agent: [],
      };
      for (const row of rows) {
        const kind = String(row?.kind || "").trim().toLowerCase();
        if (Object.prototype.hasOwnProperty.call(grouped, kind)) {
          grouped[kind].push(row);
        } else {
          grouped.agent.push(row);
        }
      }
      const nextPositions = {};
      for (const col of columns) {
        const list = grouped[col.kind]
          .slice()
          .sort((a, b) => {
            const laneA = String(a?.lane || "");
            const laneB = String(b?.lane || "");
            if (laneA !== laneB) return laneA.localeCompare(laneB);
            return String(a?.label || "").localeCompare(String(b?.label || ""));
          });
        if (!list.length) {
          continue;
        }
        const usableHeight = AGENT_GRAPH_VIEW_HEIGHT - 130;
        const spacing = list.length <= 1
          ? 0
          : Math.max(88, Math.min(150, usableHeight / Math.max(1, list.length - 1)));
        const startY = list.length <= 1
          ? AGENT_GRAPH_VIEW_HEIGHT / 2
          : Math.max(70, (AGENT_GRAPH_VIEW_HEIGHT - spacing * (list.length - 1)) / 2);
        for (let idx = 0; idx < list.length; idx += 1) {
          const node = list[idx] || {};
          const id = String(node.id || "").trim();
          if (!id) {
            continue;
          }
          const existing = previous[id];
          if (existing && Number.isFinite(Number(existing.x)) && Number.isFinite(Number(existing.y))) {
            nextPositions[id] = {
              x: Number(existing.x),
              y: Number(existing.y),
            };
          } else {
            nextPositions[id] = {
              x: col.x,
              y: startY + idx * spacing,
            };
          }
        }
      }
      this.agentGraphPositions = nextPositions;

      const selectedId = String(this.agentGraphSelectedNodeId || "").trim();
      const availableIds = new Set(rows.map((row) => String(row?.id || "").trim()).filter(Boolean));
      if (!selectedId || !availableIds.has(selectedId)) {
        this.agentGraphSelectedNodeId = rows.length ? String(rows[0]?.id || "").trim() : "";
      }
    },

    async refreshAgentGraph() {
      this.agentGraphLoading = true;
      this.agentGraphError = "";
      try {
        const payload = await this.apiGet("/api/panel/agent-graph", { timeoutMs: 7000 });
        const nextData = blankAgentGraphData();
        nextData.generated_at = String(payload?.generated_at || "").trim();
        nextData.summary = payload?.summary && typeof payload.summary === "object"
          ? {
            active_jobs: Number(payload.summary.active_jobs || 0),
            foraging_jobs: Number(payload.summary.foraging_jobs || 0),
            building_jobs: Number(payload.summary.building_jobs || 0),
            active_agents: Number(payload.summary.active_agents || 0),
            foraging_active_agents: Number(payload.summary.foraging_active_agents || 0),
            building_active_agents: Number(payload.summary.building_active_agents || 0),
          }
          : nextData.summary;
        nextData.nodes = Array.isArray(payload?.nodes)
          ? payload.nodes.map((row) => ({
            id: String(row?.id || "").trim(),
            label: String(row?.label || "").trim() || "Node",
            kind: String(row?.kind || "agent").trim().toLowerCase(),
            lane: String(row?.lane || "").trim().toLowerCase(),
            status: String(row?.status || "active").trim().toLowerCase(),
            subtitle: String(row?.subtitle || "").trim(),
            meta: row?.meta && typeof row.meta === "object" ? row.meta : {},
          })).filter((row) => row.id)
          : [];
        nextData.edges = Array.isArray(payload?.edges)
          ? payload.edges
            .map((row) => ({
              source: String(row?.source || "").trim(),
              target: String(row?.target || "").trim(),
              label: String(row?.label || "").trim(),
            }))
            .filter((row) => row.source && row.target)
          : [];
        this.agentGraphData = nextData;
        this.seedAgentGraphLayout();
      } catch (err) {
        this.agentGraphError = String(err?.message || err || "Could not load Agent Graph.");
      } finally {
        this.agentGraphLoading = false;
      }
    },

    openFamilyProfileModal() {
      this.chatMenuOpen = false;
      if (!this.auth.profile || !this.auth.profile.is_owner) {
        window.alert("Only the owner profile can add member logins.");
        return;
      }
      this.closeWaypointEntryModals();
      this.familyProfileForm = {
        username: "",
        display_name: "",
        role: "adult",
        color: this.sanitizeHexColor(this.auth?.profile?.color || "#4285f4", "#4285f4"),
        pin: "",
        pin_confirm: "",
      };
      this.familyProfileSubmitting = false;
      this.familyProfileModalOpen = true;
      this.updateBodyClasses();
      this.$nextTick(() => {
        const node = document.querySelector(".family-profile-modal input");
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    closeFamilyProfileModal() {
      this.familyProfileModalOpen = false;
      this.familyProfileSubmitting = false;
      this.updateBodyClasses();
    },

    async openEmailSettingsModal() {
      this.chatMenuOpen = false;
      this.emailSettingsSubmitting = false;
      this.emailSettingsForm = { notification_email: "", smtp_user: "", smtp_password: "", dnd_enabled: false, dnd_start: "22:00", dnd_end: "08:00" };
      try {
        const payload = await this.apiGet("/api/owner/email-settings");
        if (payload && payload.settings) {
          this.emailSettingsForm.notification_email = payload.settings.notification_email || "";
          this.emailSettingsForm.smtp_user = payload.settings.smtp_user || "";
          this.emailSettingsForm.dnd_enabled = Boolean(payload.settings.dnd_enabled);
          this.emailSettingsForm.dnd_start = payload.settings.dnd_start || "22:00";
          this.emailSettingsForm.dnd_end = payload.settings.dnd_end || "08:00";
        }
      } catch (_) {}
      this.emailSettingsModalOpen = true;
      this.updateBodyClasses();
    },

    closeEmailSettingsModal() {
      this.emailSettingsModalOpen = false;
      this.updateBodyClasses();
    },

    async openMorningDigestModal() {
      try {
        const data = await this.apiGet("/api/settings/morning-digest");
        this.digestSettings.enabled = Boolean(data.morning_digest_enabled);
        this.digestSettings.hour = Number(data.morning_digest_hour ?? 7);
        this.digestSettings.locationLabel = String(data.digest_location_label || "");
        this.digestSettings.locationLat = data.digest_location_lat ?? null;
        this.digestSettings.locationLon = data.digest_location_lon ?? null;
      } catch (_e) {}
      this.morningDigestModalOpen = true;
      this.updateBodyClasses();
    },

    closeMorningDigestModal() {
      this.morningDigestModalOpen = false;
      this.updateBodyClasses();
    },

    async openBotSettingsModal() {
      this.botSettingsSubmitting = false;
      this.botConfig = { telegram: { enabled: false, bot_token: "" }, discord: { enabled: false, bot_token: "" } };
      this.botMappings = [];
      this.botPending = [];
      this.botUserForm = { platform: "telegram", platform_user_id: "", platform_username: "", oathweaver_user_id: "" };
      try {
        const [cfgData, usersData, pendingData, profilesData] = await Promise.all([
          this.apiGet("/api/owner/bot-config"),
          this.apiGet("/api/owner/bot-users"),
          this.apiGet("/api/owner/bot-users/pending"),
          this.apiGet("/api/family/profiles"),
        ]);
        if (cfgData && cfgData.config) {
          if (cfgData.config.telegram) this.botConfig.telegram.enabled = Boolean(cfgData.config.telegram.enabled);
          if (cfgData.config.discord) this.botConfig.discord.enabled = Boolean(cfgData.config.discord.enabled);
        }
        if (usersData && Array.isArray(usersData.mappings)) this.botMappings = usersData.mappings;
        if (pendingData && Array.isArray(pendingData.pending)) this.botPending = pendingData.pending;
        if (profilesData && Array.isArray(profilesData.profiles)) this.botProfiles = profilesData.profiles;
      } catch (_) {}
      this.botSettingsModalOpen = true;
      this.updateBodyClasses();
    },

    closeBotSettingsModal() {
      this.botSettingsModalOpen = false;
      this.updateBodyClasses();
    },

    async saveBotSettings() {
      this.botSettingsSubmitting = true;
      try {
        const payload = {
          telegram: { enabled: this.botConfig.telegram.enabled },
          discord: { enabled: this.botConfig.discord.enabled },
        };
        if (this.botConfig.telegram.bot_token) payload.telegram.bot_token = this.botConfig.telegram.bot_token;
        if (this.botConfig.discord.bot_token) payload.discord.bot_token = this.botConfig.discord.bot_token;
        await this.apiPost("/api/owner/bot-config", payload);
      } catch (_) {}
      this.botSettingsSubmitting = false;
      this.closeBotSettingsModal();
    },

    async addBotUser() {
      if (!this.botUserForm.platform_user_id || !this.botUserForm.oathweaver_user_id) return;
      this.botSettingsSubmitting = true;
      try {
        const data = await this.apiPost("/api/owner/bot-users", {
          platform: this.botUserForm.platform,
          platform_user_id: this.botUserForm.platform_user_id.trim(),
          platform_username: this.botUserForm.platform_username.trim() || this.botUserForm.platform_user_id.trim(),
          oathweaver_user_id: this.botUserForm.oathweaver_user_id,
        });
        if (data && data.mapping) this.botMappings.push(data.mapping);
        this.botUserForm = { platform: "telegram", platform_user_id: "", platform_username: "", oathweaver_user_id: "" };
      } catch (_) {}
      this.botSettingsSubmitting = false;
    },

    async deleteBotUser(mappingId) {
      try {
        await this.apiDelete(`/api/owner/bot-users/${mappingId}`);
        this.botMappings = this.botMappings.filter((m) => m.id !== mappingId);
      } catch (_) {}
    },

    prefillBotUser(pending) {
      this.botUserForm.platform = pending.platform;
      this.botUserForm.platform_user_id = pending.platform_user_id;
      this.botUserForm.platform_username = pending.platform_username || "";
    },

    async saveDigestSettings() {
      try {
        await this.apiPost("/api/settings/morning-digest", {
          morning_digest_enabled: Boolean(this.digestSettings.enabled),
          morning_digest_hour: Number(this.digestSettings.hour),
        });
      } catch (_e) {}
    },

    async saveDigestLocation() {
      const query = String(this.digestLocationDraft || "").trim();
      if (!query) return;
      try {
        const geo = await this.geocodeHomeWeatherLocation(query);
        await this.apiPost("/api/settings/morning-digest", {
          digest_location_lat: geo.latitude,
          digest_location_lon: geo.longitude,
          digest_location_label: geo.label,
        });
        this.digestSettings.locationLabel = geo.label;
        this.digestSettings.locationLat = geo.latitude;
        this.digestSettings.locationLon = geo.longitude;
        this.digestLocationDraft = "";
      } catch (err) {
        window.alert("Location lookup failed: " + String(err.message || err));
      }
    },

    async submitEmailSettings() {
      this.emailSettingsSubmitting = true;
      try {
        await this.apiPost("/api/owner/email-settings", {
          notification_email: this.emailSettingsForm.notification_email.trim(),
          smtp_user: this.emailSettingsForm.smtp_user.trim(),
          smtp_password: this.emailSettingsForm.smtp_password,
          dnd_enabled: Boolean(this.emailSettingsForm.dnd_enabled),
          dnd_start: this.emailSettingsForm.dnd_start || "22:00",
          dnd_end: this.emailSettingsForm.dnd_end || "08:00",
        });
        this.closeEmailSettingsModal();
        window.alert("Email notification settings saved.");
      } catch (err) {
        window.alert("Could not save: " + String(err.message || err));
      } finally {
        this.emailSettingsSubmitting = false;
      }
    },

    async testEmailSettings() {
      this.emailSettingsSubmitting = true;
      try {
        await this.apiPost("/api/owner/email-settings", {
          notification_email: this.emailSettingsForm.notification_email.trim(),
          smtp_user: this.emailSettingsForm.smtp_user.trim(),
          smtp_password: this.emailSettingsForm.smtp_password,
          dnd_enabled: Boolean(this.emailSettingsForm.dnd_enabled),
          dnd_start: this.emailSettingsForm.dnd_start || "22:00",
          dnd_end: this.emailSettingsForm.dnd_end || "08:00",
        });
        await this.apiPost("/api/owner/email-settings/test", {});
        window.alert("Test email sent! Check your inbox.");
      } catch (err) {
        window.alert("Test failed: " + String(err.message || err));
      } finally {
        this.emailSettingsSubmitting = false;
      }
    },

    async submitFamilyProfileModal() {
      if (!this.auth.profile || !this.auth.profile.is_owner) {
        window.alert("Only the owner profile can add member logins.");
        return;
      }
      const username = String(this.familyProfileForm.username || "").trim();
      const displayName = String(this.familyProfileForm.display_name || "").trim() || username;
      const roleRaw = String(this.familyProfileForm.role || "adult").trim().toLowerCase();
      const role = roleRaw === "child" ? "child" : "adult";
      const color = this.sanitizeHexColor(this.familyProfileForm.color, "#4285f4");
      const pin = String(this.familyProfileForm.pin || "").trim();
      const pinConfirm = String(this.familyProfileForm.pin_confirm || "").trim();
      if (!username) {
        window.alert("Username is required.");
        return;
      }
      if (!this.isFourDigitPin(pin)) {
        window.alert("PIN must be exactly 4 digits.");
        return;
      }
      if (pin !== pinConfirm) {
        window.alert("PIN and confirmation do not match.");
        return;
      }
      this.familyProfileSubmitting = true;
      try {
        const payload = await this.apiPost("/api/family/profiles", {
          username,
          display_name: displayName,
          role,
          color,
          pin,
        });
        const created = payload?.profile || {};
        this.closeFamilyProfileModal();
        window.alert(
          `Created profile: ${String(created.display_name || created.username || username)}\n` +
            `Username: ${String(created.username || username)}\n` +
            "Share the username and PIN with that person."
        );
      } catch (err) {
        window.alert(`Could not create profile: ${String(err.message || err)}`);
      } finally {
        this.familyProfileSubmitting = false;
      }
    },

    async lockSession() {
      this.chatMenuOpen = false;
      if (!this.auth.enabled) {
        window.alert("Session lock is disabled.");
        return;
      }
      await this.apiPost("/api/auth/logout", {});
      window.location.reload();
    },

    markConversationCancelRequested(conversationId, value = true) {
      const id = String(conversationId || "").trim();
      if (!id) {
        return;
      }
      const meta = this.conversationSendingMeta(id);
      if (!meta) {
        return;
      }
      this.setConversationSending(id, Object.assign({}, meta, { cancelRequested: Boolean(value) }));
    },

    async cancelActiveThinking() {
      const conversationId = String(this.activeConversationId || "").trim();
      if (!conversationId) {
        return;
      }
      const meta = this.conversationSendingMeta(conversationId);
      if (!meta || !meta.requestId || Boolean(meta.cancelRequested)) {
        return;
      }
      this.markConversationCancelRequested(conversationId, true);
      try {
        const payload = await this.apiPost(`/api/jobs/${encodeURIComponent(meta.requestId)}/cancel`, {
          conversation_id: conversationId,
        });
        const summary = String(payload?.summary || "").trim();
        if (String(this.activeConversationId || "").trim() === conversationId) {
          const existing = Array.isArray(this.activeConversation?.messages) ? this.activeConversation.messages.slice() : [];
          existing.push({
            id: `cancel_${Date.now()}`,
            role: "assistant",
            content: summary ? `Stopped.\n\n${summary}` : "Stopped.",
            ts: new Date().toISOString(),
            canceled: true,
          });
          this.activeConversation = Object.assign({}, this.activeConversation || {}, { messages: existing });
          this.$nextTick(() => this.scrollMessages());
        }
      } catch (err) {
        this.markConversationCancelRequested(conversationId, false);
        window.alert(`Cancel failed: ${String(err.message || err)}`);
      }
    },

    deleteMessageFromChat(msgId) {
      const id = String(msgId || "").trim();
      if (!id || !Array.isArray(this.activeConversation?.messages)) return;
      const filtered = this.activeConversation.messages.filter((m) => String(m?.id || "") !== id);
      this.activeConversation = Object.assign({}, this.activeConversation, { messages: filtered });
    },

    async sendMessage(queuedItem = null) {
      const looksLikeDomEvent = Boolean(
        queuedItem
        && typeof queuedItem === "object"
        && (
          typeof queuedItem.preventDefault === "function"
          || typeof queuedItem.stopPropagation === "function"
          || queuedItem instanceof Event
        )
      );
      if (looksLikeDomEvent) {
        queuedItem = null;
      }
      const fromQueue = Boolean(
        queuedItem
        && typeof queuedItem === "object"
        && Object.prototype.hasOwnProperty.call(queuedItem, "conversationId")
      );
      const conversationId = String((fromQueue ? queuedItem?.conversationId : this.activeConversationId) || "").trim();
      if (!conversationId) {
        return false;
      }
      this.closeBlockingOverlaysForStreaming();
      if (!fromQueue && this.isConversationSending(conversationId)) {
        return this.queueComposerMessage();
      }
      if (fromQueue && this.isConversationSending(conversationId)) {
        return false;
      }
      const typedContent = fromQueue ? String(queuedItem?.content || "").trim() : String(this.draft || "").trim();
      const imageRows = fromQueue
        ? (Array.isArray(queuedItem?.imageRows) ? queuedItem.imageRows.slice() : [])
        : (Array.isArray(this.composerImages) ? this.composerImages.slice() : []);
      const selectedLoras = this.normalizeLoraSelection(fromQueue ? queuedItem?.selectedLoras || [] : this.composerSelectedLoras);
      const imageStyle = String(fromQueue ? queuedItem?.imageStyle || "" : "").trim() || (selectedLoras.length ? "lora" : "realistic");
      if (!fromQueue) {
        this.composerSelectedLoras = selectedLoras;
        this.composerImageStyle = imageStyle;
      }
      if (!typedContent && imageRows.length === 0) {
        return false;
      }

      const sendMode = fromQueue
        ? (String(queuedItem?.mode || "talk").trim() || "talk")
        : (this.inputMode === "forage"
          ? "forage"
          : (this.inputMode === "make" ? "make" : (this.inputMode === "plan" ? "plan" : "talk")));
      const likelyForagingRequest = sendMode === "forage";
      const likelyRenderRequest = false;
      const extendsRequestId = sendMode === "make"
        ? String(this.pendingExtendsRequestId || "").trim()
        : "";
      let requestId = "";
      try {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          requestId = String(window.crypto.randomUUID());
        }
      } catch (_err) {}
      if (!requestId) {
        requestId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      }
      this.setConversationSending(conversationId, {
        requestId,
        startedAt: Date.now(),
        cancelRequested: false,
        foraging: likelyForagingRequest,
        renderJob: likelyRenderRequest,
      });

      // Start parallel event-poll so the think stream updates while the POST is in-flight.
      let _streamPollActive = true;
      (async () => {
        await this.waitMs(500);
        while (_streamPollActive) {
          try {
            const jp = await this.apiGet(`/api/jobs/${encodeURIComponent(requestId)}`, { timeoutMs: 3500 });
            if (jp?.job) {
              const job = jp.job;
              if (Array.isArray(job.events) && job.events.length > 0) {
                const ne = Object.assign({}, this.pendingJobEvents);
                ne[conversationId] = job.events;
                this.pendingJobEvents = ne;
              }
              if (job.agent_tracker && typeof job.agent_tracker === "object") {
                const nt = Object.assign({}, this.pendingJobAgentTracker);
                nt[conversationId] = job.agent_tracker;
                this.pendingJobAgentTracker = nt;
              }
              if (Array.isArray(job.live_sources) && job.live_sources.length > 0) {
                const nl = Object.assign({}, this.pendingLiveSources);
                nl[conversationId] = job.live_sources;
                this.pendingLiveSources = nl;
              }
              const ns = Object.assign({}, this.sendingJobStage);
              ns[conversationId] = { stage: job.stage || "", label: this._humanizeJobStage(job) };
              this.sendingJobStage = ns;
            }
          } catch (_pollErr) {}
          if (_streamPollActive) await this.waitMs(1500);
        }
      })();

      if (sendMode === "forage" || sendMode === "make" || sendMode === "plan") {
        // Reset globally to Talk as soon as a Discovery/Make request is sent.
        // This avoids accidentally sending subsequent turns in the wrong mode.
        this.resetComposerMode();
      }
      this.chatMenuOpen = false;
      const replyTarget = fromQueue
        ? (queuedItem?.replyTarget && typeof queuedItem.replyTarget === "object" ? Object.assign({}, queuedItem.replyTarget) : null)
        : (this.replyTargetMsg || null);
      if (!fromQueue) {
        this.composerAddMenuOpen = false;
        this.draft = "";
        this.saveDraftForConversation(conversationId);
        this.composerImages = [];
        this.replyTargetMsg = null;
        this.saveComposerStateForConversation(conversationId);
        if (this.$refs.imageInput) {
          this.$refs.imageInput.value = "";
        }
        if (this.$refs.fileInput) {
          this.$refs.fileInput.value = "";
        }
        this.resizeComposer();
      }
      let sentSuccessfully = false;
      try {
        const existing = Array.isArray(this.activeConversation?.messages) ? this.activeConversation.messages.slice() : [];
        const localMsg = {
          id: `local_user_${Date.now()}`,
          role: "user",
          content: typedContent || `Uploaded ${imageRows.length} file(s).`,
          mode: sendMode,
          foraging: likelyForagingRequest,
          attachments: imageRows.map((row) => ({
            id: row.id,
            type: row.isDoc ? "document" : "image",
            name: row.name,
            url: row.previewUrl,
            mime: row.type,
            size: row.size,
            local_only: true,
          })),
          ts: new Date().toISOString(),
          local_only: true,
        };
        if (replyTarget) localMsg.reply_to = replyTarget;
        existing.push(localMsg);
        this.activeConversation = Object.assign({}, this.activeConversation || {}, { messages: existing });
      } catch (_err) {}
      this.$nextTick(() => this.scrollMessages());

      try {
        let payload = null;
        if (imageRows.length > 0) {
          const formData = new FormData();
          formData.append("content", typedContent);
          formData.append("mode", sendMode);
          formData.append("request_id", requestId);
          formData.append("image_style", imageStyle);
          formData.append("selected_loras", JSON.stringify(selectedLoras));
          if ((sendMode === "make" || sendMode === "plan") && this.makeType) {
            formData.append("make_type", this.makeType);
          }
          if (sendMode === "make" && extendsRequestId) {
            formData.append("extends_request_id", extendsRequestId);
          }
          for (const row of imageRows) {
            if (row?.file) {
              formData.append("images", row.file, row.name || "image");
            }
          }
          payload = await this.apiPostForm(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, formData);
        } else {
          const jsonBody = {
            content: typedContent,
            mode: sendMode,
            request_id: requestId,
            image_style: imageStyle,
            selected_loras: selectedLoras,
          };
          if ((sendMode === "make" || sendMode === "plan") && this.makeType) {
            jsonBody.make_type = this.makeType;
          }
          if (sendMode === "make" && extendsRequestId) {
            jsonBody.extends_request_id = extendsRequestId;
          }
          if (replyTarget) jsonBody.reply_to = replyTarget;
          payload = await this.apiPost(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, jsonBody);
        }
        const convo = payload.conversation || null;
        if (convo) {
          if (String(this.activeConversationId || "").trim() === conversationId) {
            this.activeConversation = convo;
            this.activeConversationId = convo.id;
            this.syncImagePrefsFromConversation(convo);
            this.setActiveProject(convo.project || this.activeProject);
            this.activeTopicId = normalizeTopicId(convo.topic_id || this.activeTopicId);
            this.startAssistantTypewriterFromConversation(convo, requestId);
            // TTS: speak the last assistant reply
            try {
              const msgs = Array.isArray(convo.messages) ? convo.messages : [];
              const lastAssistant = [...msgs].reverse().find((m) => m?.role === "assistant");
              if (lastAssistant?.content) this.speakText(lastAssistant.content);
            } catch (_e) {}
          }
        }
        _streamPollActive = false;
        sentSuccessfully = true;
        if (sendMode === "make" && extendsRequestId) {
          this.clearPendingMakeOutputExtension();
        }
        if (!fromQueue) {
          this.resetComposerMode();
        }
        await this.markConversationRead(conversationId, { refreshList: false });
        try {
          await this.refreshConversations();
        } catch (refreshErr) {
          console.warn("Post-send conversation refresh failed:", refreshErr);
        }
        try {
          await this.refreshPanelBadges();
        } catch (refreshErr) {
          console.warn("Post-send panel refresh failed:", refreshErr);
        }
      } catch (err) {
        _streamPollActive = false;
        let recovered = false;
        if (this.isLikelyNetworkDropError(err)) {
          recovered = await this.recoverMessageRequest(conversationId, requestId, likelyForagingRequest);
        }
        if (recovered) {
          sentSuccessfully = true;
          if (!fromQueue) {
            this.resetComposerMode();
          }
        } else {
          if (imageRows.length > 0) {
            if (fromQueue) {
              queuedItem.imageRows = imageRows.slice();
            } else {
              this.composerImages = imageRows;
            }
          }
          if (!fromQueue) {
            this.replyTargetMsg = replyTarget && typeof replyTarget === "object" ? Object.assign({}, replyTarget) : null;
            this.saveComposerStateForConversation(conversationId);
          }
          if (!sentSuccessfully && String(this.activeConversationId || "").trim() === conversationId) {
            const existing = Array.isArray(this.activeConversation?.messages) ? this.activeConversation.messages.slice() : [];
            existing.push({
              id: `err_${Date.now()}`,
              role: "assistant",
              content: `Error: ${String(err.message || err)}`,
              ts: new Date().toISOString(),
            });
            this.activeConversation = Object.assign({}, this.activeConversation || {}, { messages: existing });
          } else {
            console.warn("Message sent, but a post-send operation failed:", err);
          }
        }
      } finally {
        _streamPollActive = false;
        if (sentSuccessfully) {
          for (const row of imageRows) {
            if (row?.previewUrl) {
              URL.revokeObjectURL(row.previewUrl);
            }
          }
        }
        this.setConversationSending(conversationId, false);
        if (sentSuccessfully) {
          await this.flushConversationQueue(conversationId);
        }
        if (String(this.activeConversationId || "").trim() === conversationId) {
          this.$nextTick(() => this.scrollMessages());
        }
      }
      return sentSuccessfully;
    },

    waypointEventTimeLabel(row) {
      const start = normalizeTimeText(row?.start_time || "");
      const end = normalizeTimeText(row?.end_time || "");
      if (start && end) {
        return `${start}-${end}`;
      }
      if (start) {
        return start;
      }
      if (end) {
        return `until ${end}`;
      }
      return "All day";
    },

    normalizeWaypointMemberIds(raw) {
      const values = Array.isArray(raw) ? raw : [];
      const result = [];
      const seen = new Set();
      for (const item of values) {
        const id = String(item || "").trim();
        if (!id || seen.has(id)) {
          continue;
        }
        seen.add(id);
        result.push(id);
      }
      return result;
    },

    waypointMemberNamesFromIds(raw) {
      const ids = this.normalizeWaypointMemberIds(raw);
      if (!ids.length) {
        return [];
      }
      const members = Array.isArray(this.waypoint?.members) ? this.waypoint.members : [];
      const byId = new Map();
      for (const row of members) {
        const id = String(row?.id || "").trim();
        if (!id) {
          continue;
        }
        byId.set(id, String(row?.name || row?.username || id).trim());
      }
      const names = [];
      for (const id of ids) {
        const name = String(byId.get(id) || "").trim();
        if (name) {
          names.push(name);
        }
      }
      return names;
    },

    waypointRowMatchesMemberFilter(row) {
      const selectedIds = this.normalizeWaypointMemberIds(this.waypointCalendarFilteredMemberIds || []);
      if (!selectedIds.length) {
        return true;
      }
      const rowIds = this.normalizeWaypointMemberIds(row?.member_ids || []);
      if (!rowIds.length) {
        return false;
      }
      const selected = new Set(selectedIds);
      return rowIds.some((id) => selected.has(id));
    },

    toggleWaypointCalendarMemberFilter() {
      const nowOpen = !this.waypointCalendarMemberFilterOpen;
      this.waypointCalendarMemberFilterOpen = nowOpen;
      if (nowOpen) {
        this.$nextTick(() => {
          const btn = document.querySelector(".waypoint-member-filter-btn");
          if (!btn) return;
          const rect = btn.getBoundingClientRect();
          const popW = Math.min(320, window.innerWidth * 0.88);
          // Right-align to button's right edge; clamp left edge to 8px margin
          let rightEdge = window.innerWidth - rect.right;
          if (rect.right - popW < 8) rightEdge = window.innerWidth - popW - 8;
          this.waypointMemberFilterPopStyle = {
            position: "fixed",
            top: (rect.bottom + 6) + "px",
            right: Math.max(0, rightEdge) + "px",
            left: "auto",
            transform: "none",
            width: popW + "px",
            zIndex: "300",
          };
        });
      } else {
        this.waypointMemberFilterPopStyle = {};
      }
    },

    closeWaypointCalendarMemberFilter() {
      this.waypointCalendarMemberFilterOpen = false;
    },

    waypointCalendarFilterToggleMember(memberId) {
      const id = String(memberId || "").trim();
      if (!id) {
        return;
      }
      const selected = new Set(this.normalizeWaypointMemberIds(this.waypointCalendarFilteredMemberIds || []));
      if (selected.has(id)) {
        selected.delete(id);
      } else {
        selected.add(id);
      }
      this.waypointCalendarFilteredMemberIds = Array.from(selected);
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    waypointCalendarFilterSelectAll() {
      this.waypointCalendarFilteredMemberIds = [];
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    waypointCalendarFilterOnly(memberId) {
      const id = String(memberId || "").trim();
      if (!id) {
        return;
      }
      this.waypointCalendarFilteredMemberIds = [id];
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    toggleWaypointMonthPreview() {
      if (!this.waypointCanShowMonthPreview) {
        this.waypointMonthPreviewOpen = false;
        return;
      }
      this.waypointMonthPreviewOpen = !this.waypointMonthPreviewOpen;
    },

    buildWaypointMonthPreviewReport() {
      const empty = {
        title: "No events scheduled for this month.",
        highlights: [],
        recurring: [],
        conflicts: [],
        patterns: [],
      };
      if (!this.waypointCanShowMonthPreview) {
        return empty;
      }

      const anchor = startOfLocalDay(this.waypointCalendarDate || new Date());
      const year = anchor.getFullYear();
      const month = anchor.getMonth();
      const monthRows = this.waypointCalendarEntries()
        .filter((row) => {
          const d = parseDateKey(String(row?.date || "").trim());
          return d && d.getFullYear() === year && d.getMonth() === month;
        })
        .slice()
        .sort((a, b) => {
          const ad = String(a?.date || "");
          const bd = String(b?.date || "");
          if (ad !== bd) {
            return ad.localeCompare(bd);
          }
          const at = timeTextToMinutes(a?.start_time);
          const bt = timeTextToMinutes(b?.start_time);
          if (at !== bt) {
            return at - bt;
          }
          return String(a?.title || "").localeCompare(String(b?.title || ""));
        });
      if (!monthRows.length) {
        return empty;
      }

      const title = `${anchor.toLocaleDateString(undefined, { month: "long", year: "numeric" })} preview`;
      const highlights = monthRows.slice(0, 5).map((row) => {
        const d = parseDateKey(String(row?.date || "").trim());
        const dayLabel = d
          ? d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
          : String(row?.date || "");
        const timeLabel = this.waypointEventTimeLabel(row) || "Anytime";
        return `${dayLabel} • ${timeLabel} • ${String(row?.title || "Event")}`;
      });

      const recurring = [];
      const recurringMap = new Map();
      for (const row of monthRows) {
        const key = `${String(row?.source || "event")}::${String(row?.title || "").trim().toLowerCase()}`;
        if (!String(row?.title || "").trim()) {
          continue;
        }
        if (!recurringMap.has(key)) {
          recurringMap.set(key, []);
        }
        recurringMap.get(key).push(String(row?.date || "").trim());
      }
      for (const [key, dates] of recurringMap.entries()) {
        const uniqDates = Array.from(new Set(dates)).filter(isIsoDate).sort();
        if (uniqDates.length < 2) {
          continue;
        }
        const titleText = key.split("::")[1] || "Recurring";
        const dayDiffs = [];
        for (let i = 1; i < uniqDates.length; i += 1) {
          const prev = parseDateKey(uniqDates[i - 1]);
          const next = parseDateKey(uniqDates[i]);
          if (!prev || !next) {
            continue;
          }
          dayDiffs.push(Math.round((next.getTime() - prev.getTime()) / 86400000));
        }
        let cadence = `${uniqDates.length}x this month`;
        if (dayDiffs.length && dayDiffs.every((x) => Math.abs(x - 7) <= 1)) {
          cadence = "weekly";
        } else if (dayDiffs.length && dayDiffs.every((x) => Math.abs(x - 14) <= 1)) {
          cadence = "biweekly";
        }
        recurring.push(`${titleText} (${cadence})`);
      }

      const members = Array.isArray(this.waypoint?.members) ? this.waypoint.members : [];
      const roleById = new Map();
      for (const member of members) {
        const id = String(member?.id || "").trim();
        if (!id) {
          continue;
        }
        roleById.set(id, String(member?.member_role || "adult").trim().toLowerCase() || "adult");
      }

      const byDate = new Map();
      for (const row of monthRows) {
        const dateKey = String(row?.date || "").trim();
        if (!isIsoDate(dateKey)) {
          continue;
        }
        if (!byDate.has(dateKey)) {
          byDate.set(dateKey, []);
        }
        byDate.get(dateKey).push(row);
      }

      const conflicts = [];
      for (const [dateKey, rows] of byDate.entries()) {
        let adultHeavy = false;
        let childOnlyCount = 0;
        for (const row of rows) {
          const memberIds = this.normalizeWaypointMemberIds(row?.member_ids || []);
          if (!memberIds.length) {
            continue;
          }
          const adultCount = memberIds.filter((id) => roleById.get(id) !== "child").length;
          const childCount = memberIds.filter((id) => roleById.get(id) === "child").length;
          if (adultCount >= 2) {
            adultHeavy = true;
          }
          if (childCount >= 1 && adultCount === 0) {
            childOnlyCount += 1;
          }
        }
        if (adultHeavy && childOnlyCount >= 1) {
          conflicts.push(
            `${dateKey}: parents appear booked while child events run too. Confirm coverage and assign a contact host if needed.`
          );
        }
      }

      const patterns = [];
      const patternRows = Array.isArray(this.waypoint?.event_patterns) ? this.waypoint.event_patterns : [];
      for (const row of patternRows) {
        const titleText = String(row?.title || "").trim();
        if (!titleText) {
          continue;
        }
        const rescheduledCount = Number(row?.rescheduled_count || 0);
        const canceledCount = Number(row?.canceled_count || 0);
        if (rescheduledCount >= 2) {
          patterns.push(`${titleText} has been rescheduled ${rescheduledCount} times. Consider a more realistic slot.`);
        }
        if (canceledCount >= 2) {
          patterns.push(`${titleText} has been canceled ${canceledCount} times. Consider removing or reframing it.`);
        }
        if (patterns.length >= 3) {
          break;
        }
      }

      return {
        title,
        highlights,
        recurring,
        conflicts,
        patterns,
      };
    },

    waypointTaskAssigneeLabel(task) {
      const names = this.waypointMemberNamesFromIds(task?.member_ids || []);
      if (names.length) {
        return names.join(", ");
      }
      const fallback = Array.isArray(task?.member_names) ? task.member_names : [];
      return fallback
        .map((x) => String(x || "").trim())
        .filter(Boolean)
        .join(", ");
    },

    waypointEventAttendeeLabel(eventRow) {
      const names = this.waypointMemberNamesFromIds(eventRow?.member_ids || []);
      if (names.length) {
        return names.join(", ");
      }
      const fallback = Array.isArray(eventRow?.member_names) ? eventRow.member_names : [];
      return fallback
        .map((x) => String(x || "").trim())
        .filter(Boolean)
        .join(", ");
    },

    waypointReminderTimeLabel(task) {
      const notes = String(task?.notes || "");
      const match = notes.match(/remind_at\s*=\s*([0-2]\d:[0-5]\d)/i);
      if (!match) {
        return "";
      }
      return String(match[1] || "");
    },

    extractReminderTimeFromNotes(notesText) {
      const notes = String(notesText || "");
      const match = notes.match(/remind_at\s*=\s*([0-2]\d:[0-5]\d)/i);
      if (!match) {
        return "";
      }
      return String(match[1] || "");
    },

    waypointDefaultRecurrenceWeekdayForDate(dateKey) {
      const parsed = parseDateKey(String(dateKey || "").trim());
      return parsed ? jsDayToMonday0(parsed.getDay()) : jsDayToMonday0(startOfLocalDay(new Date()).getDay());
    },

    waypointDefaultRecurrenceNthForDate(dateKey) {
      const parsed = parseDateKey(String(dateKey || "").trim());
      const day = parsed ? parsed.getDate() : startOfLocalDay(new Date()).getDate();
      return Math.max(1, Math.min(5, Math.floor((day - 1) / 7) + 1));
    },

    normalizeWaypointEventRecurrence(row) {
      const baseDate = parseDateKey(String(row?.date || "").trim()) || startOfLocalDay(new Date());
      const type = normalizeRecurrenceType(row?.recurrence_type);
      const enabledRaw = row?.recurrence_enabled;
      let enabled = Boolean(enabledRaw);
      if (typeof enabledRaw === "string") {
        enabled = ["1", "true", "yes", "y", "on"].includes(enabledRaw.trim().toLowerCase());
      }
      if (type === "none") {
        enabled = false;
      }
      const interval = Math.max(1, Math.min(12, Number.parseInt(row?.recurrence_interval, 10) || 1));
      const weekdayRaw = Number.parseInt(row?.recurrence_weekday, 10);
      const weekday = Number.isFinite(weekdayRaw)
        ? Math.max(0, Math.min(6, weekdayRaw))
        : jsDayToMonday0(baseDate.getDay());
      const day = Math.max(1, Math.min(31, Number.parseInt(row?.recurrence_day, 10) || baseDate.getDate()));
      const nth = Math.max(1, Math.min(5, Number.parseInt(row?.recurrence_nth, 10) || this.waypointDefaultRecurrenceNthForDate(toDateKey(baseDate))));
      const until = isIsoDate(String(row?.recurrence_until || "").trim()) ? String(row.recurrence_until).trim() : "";
      return {
        recurrence_enabled: enabled,
        recurrence_type: type,
        recurrence_interval: interval,
        recurrence_weekday: Number.isFinite(weekday) ? weekday : baseDate.getDay(),
        recurrence_day: day,
        recurrence_nth: nth,
        recurrence_until: until,
      };
    },

    expandWaypointRecurringEvents(eventRows) {
      const rows = Array.isArray(eventRows) ? eventRows : [];
      const anchor = startOfLocalDay(this.waypointCalendarDate || new Date());
      let windowStart = addDays(anchor, -7);
      let windowEnd = addMonths(anchor, 14);
      if (this.waypointCalendarView === "day") {
        windowStart = addDays(anchor, -3);
        windowEnd = addDays(anchor, 30);
      } else if (this.waypointCalendarView === "three_day") {
        windowStart = addDays(anchor, -3);
        windowEnd = addDays(anchor, 90);
      } else if (this.waypointCalendarView === "agenda") {
        windowStart = addDays(anchor, -3);
        windowEnd = addDays(anchor, 90);
      }
      const out = [];
      for (const row of rows) {
        const baseDate = parseDateKey(String(row?.date || "").trim());
        if (!baseDate) {
          continue;
        }
        const rec = this.normalizeWaypointEventRecurrence(row);
        if (!rec.recurrence_enabled || rec.recurrence_type === "none") {
          out.push(row);
          continue;
        }
        const untilDate = rec.recurrence_until ? parseDateKey(rec.recurrence_until) : null;
        const seen = new Set();
        let guard = 0;
        if (rec.recurrence_type === "weekly_day") {
          let current = startOfLocalDay(baseDate);
          const weekdayJs = monday0ToJsDay(rec.recurrence_weekday);
          const offset = (weekdayJs - current.getDay() + 7) % 7;
          if (offset) {
            current = addDays(current, offset);
          }
          while (current < windowStart && guard < 800) {
            current = addDays(current, rec.recurrence_interval * 7);
            guard += 1;
          }
          while (current <= windowEnd && guard < 800) {
            if (current >= baseDate && (!untilDate || current <= untilDate)) {
              const key = toDateKey(current);
              if (!seen.has(key)) {
                seen.add(key);
                out.push(
                  Object.assign({}, row, {
                    id: `${String(row?.id || "")}__${key}`,
                    source_id: String(row?.id || "").trim(),
                    recurrence_instance_date: key,
                    date: key,
                  })
                );
              }
            }
            current = addDays(current, rec.recurrence_interval * 7);
            guard += 1;
          }
          continue;
        }
        if (rec.recurrence_type === "monthly_day_of_month") {
          let current = new Date(baseDate.getFullYear(), baseDate.getMonth(), 1);
          while (current < new Date(windowStart.getFullYear(), windowStart.getMonth(), 1) && guard < 800) {
            current = addMonths(current, rec.recurrence_interval);
            guard += 1;
          }
          while (current <= windowEnd && guard < 800) {
            const maxDay = daysInMonth(current.getFullYear(), current.getMonth());
            const day = Math.min(rec.recurrence_day, maxDay);
            const candidate = new Date(current.getFullYear(), current.getMonth(), day);
            if (candidate >= baseDate && candidate >= windowStart && candidate <= windowEnd && (!untilDate || candidate <= untilDate)) {
              const key = toDateKey(candidate);
              if (!seen.has(key)) {
                seen.add(key);
                out.push(
                  Object.assign({}, row, {
                    id: `${String(row?.id || "")}__${key}`,
                    source_id: String(row?.id || "").trim(),
                    recurrence_instance_date: key,
                    date: key,
                  })
                );
              }
            }
            current = addMonths(current, rec.recurrence_interval);
            guard += 1;
          }
          continue;
        }
        if (rec.recurrence_type === "monthly_nth_weekday") {
          let current = new Date(baseDate.getFullYear(), baseDate.getMonth(), 1);
          while (current < new Date(windowStart.getFullYear(), windowStart.getMonth(), 1) && guard < 800) {
            current = addMonths(current, rec.recurrence_interval);
            guard += 1;
          }
          while (current <= windowEnd && guard < 800) {
            const weekdayJs = monday0ToJsDay(rec.recurrence_weekday);
            const candidate = nthWeekdayInMonth(current.getFullYear(), current.getMonth(), weekdayJs, rec.recurrence_nth);
            if (
              candidate &&
              candidate >= baseDate &&
              candidate >= windowStart &&
              candidate <= windowEnd &&
              (!untilDate || candidate <= untilDate)
            ) {
              const key = toDateKey(candidate);
              if (!seen.has(key)) {
                seen.add(key);
                out.push(
                  Object.assign({}, row, {
                    id: `${String(row?.id || "")}__${key}`,
                    source_id: String(row?.id || "").trim(),
                    recurrence_instance_date: key,
                    date: key,
                  })
                );
              }
            }
            current = addMonths(current, rec.recurrence_interval);
            guard += 1;
          }
          continue;
        }
        out.push(row);
      }
      return out;
    },

    waypointCalendarEvents() {
      const events = Array.isArray(this.waypoint?.events) ? this.waypoint.events.slice() : [];
      return events.filter((row) => {
        if (String(row?.status || "open").trim().toLowerCase() === "done") {
          return false;
        }
        const notes = String(row?.notes || "").trim();
        if (/(?:^|\s)reminder_(?:task_id|title)\s*=.+(?:\s|$)/i.test(notes)) {
          return false;
        }
        if (!this.waypointRowMatchesMemberFilter(row)) {
          return false;
        }
        return true;
      });
    },

    waypointCalendarEntries() {
      const rawEvents = this.waypointCalendarTypeFilter === "tasks"
        ? []
        : this.waypointCalendarEvents().map((row) =>
            Object.assign({}, row, { source: "event", source_id: String(row?.id || "").trim() })
          );
      const eventRows = this.expandWaypointRecurringEvents(rawEvents);
      const taskRows = this.waypointCalendarTypeFilter === "events"
        ? []
        : (Array.isArray(this.waypoint?.tasks) ? this.waypoint.tasks : [])
            .filter((task) => String(task?.status || "open").trim().toLowerCase() !== "done")
            .filter((task) => isIsoDate(String(task?.due_date || "").trim()))
            .filter((task) => this.waypointRowMatchesMemberFilter(task))
            .map((task) => {
              const timeText = this.waypointReminderTimeLabel(task);
              return {
                id: `task_${String(task?.id || "").trim()}`,
                source: "task",
                source_id: String(task?.id || "").trim(),
                title: String(task?.title || "").trim() || "Task",
                date: String(task?.due_date || "").trim(),
                start_time: timeText,
                end_time: "",
                location: "",
                notes: String(task?.notes || "").trim(),
                reminder_count: Number(task?.reminder_count || 0),
                snooze_until: String(task?.snooze_until || "").trim(),
                color: "#f4b400",
                member_ids: Array.isArray(task?.member_ids) ? task.member_ids : [],
                rolled_from_date: String(task?.rolled_from_date || "").trim(),
              };
            });
      return [...eventRows, ...taskRows];
    },

    waypointEventColor(row) {
      return this.waypointEntryColorInfo(row).borderColor;
    },

    waypointEntryColorInfo(row) {
      const isTask = String(row?.source || "").trim().toLowerCase() === "task";
      const profileFallback = this.sanitizeHexColor(
        this.waypoint?.profile_color || this.auth?.profile?.color || "#4285f4",
        "#4285f4"
      );
      const fallback = isTask ? "#f4b400" : profileFallback;
      const colorMap = this.waypointMemberColorMap;
      const memberIds = Array.isArray(row?.member_ids) ? row.member_ids : [];
      const memberColors = memberIds
        .map((id) => colorMap[String(id || "")])
        .filter((c) => c && /^#[0-9a-fA-F]{3,6}$/.test(c));
      const colors = memberColors.length
        ? memberColors
        : [this.sanitizeHexColor(String(row?.color || ""), fallback)];
      const borderColor = colors[0];
      const n = colors.length;
      const bg = n > 1
        ? `linear-gradient(90deg, ${colors.flatMap((c, i) => [`${c} ${Math.round(i * 100 / n)}%`, `${c} ${Math.round((i + 1) * 100 / n)}%`]).join(", ")})`
        : colors[0];
      return { borderColor, bg, multi: n > 1, colors };
    },

    // Builds a left-grey / right-color split gradient for panel item cards.
    // The transparent portion lets the element's navy background show through.
    waypointEntrySplitBg(ci) {
      if (ci.multi) {
        const n = ci.colors.length;
        const coloredWidth = 70;
        const startPct = 30;
        const stops = ci.colors.flatMap((c, i) => {
          const lo = Math.round(startPct + (i * coloredWidth / n));
          const hi = Math.round(startPct + ((i + 1) * coloredWidth / n));
          return [`${c} ${lo}%`, `${c} ${hi}%`];
        });
        return `linear-gradient(90deg, transparent 30%, ${stops.join(", ")}), var(--palette-navy)`;
      }
      return `linear-gradient(90deg, transparent 45%, ${ci.borderColor} 100%), var(--palette-navy)`;
    },

    waypointEntryStyle(row) {
      const ci = this.waypointEntryColorInfo(row);
      return {
        "--event-color": ci.borderColor,
        "--entry-color": ci.borderColor,
        background: this.waypointEntrySplitBg(ci),
      };
    },

    waypointEntryKindIcon(row) {
      const source = String(row?.source || "").trim().toLowerCase();
      if (source === "task") return "🔧";
      return "🗓";
    },

    waypointEntryKindLabel(row) {
      const source = String(row?.source || "").trim().toLowerCase();
      return source === "task" ? "Task" : "Event";
    },

    waypointEntryReminderText(row) {
      const source = String(row?.source || "").trim().toLowerCase();
      if (source === "task") {
        const snoozeUntil = String(row?.snooze_until || "").trim();
        if (snoozeUntil) {
          return `Snoozed until ${snoozeUntil}`;
        }
        const reminderTime = this.waypointReminderTimeLabel(row);
        if (reminderTime) {
          return `Reminder at ${reminderTime}`;
        }
        const count = Number(row?.reminder_count || 0);
        if (count > 0) {
          return `Nudges sent: ${count}`;
        }
        return "";
      }
      const notes = String(row?.notes || "");
      const match = notes.match(/remind_at\s*=\s*([0-2]\d:[0-5]\d)/i);
      const offsets = Array.isArray(row?.auto_reminder_offsets)
        ? row.auto_reminder_offsets
            .map((x) => Number(x))
            .filter((x) => Number.isFinite(x) && x > 0)
            .sort((a, b) => b - a)
        : [];
      const cadence = offsets.length
        ? `Auto ${offsets
            .map((mins) => {
              if (mins % 60 === 0) {
                const hours = mins / 60;
                return `${hours}h`;
              }
              return `${mins}m`;
            })
            .join(", ")}`
        : "";
      if (match && match[1] && cadence) {
        return `${cadence} • custom ${String(match[1])}`;
      }
      if (match && match[1]) {
        return `Reminder at ${String(match[1])}`;
      }
      if (cadence) {
        return cadence;
      }
      return "";
    },

    buildWaypointEventIndex(events) {
      const map = {};
      for (const row of events || []) {
        const key = String(row?.date || "").trim();
        if (!isIsoDate(key)) {
          continue;
        }
        if (!Array.isArray(map[key])) {
          map[key] = [];
        }
        map[key].push(row);
      }
      for (const key of Object.keys(map)) {
        map[key].sort((a, b) => {
          const aStart = normalizeTimeText(a?.start_time || "") || "99:99";
          const bStart = normalizeTimeText(b?.start_time || "") || "99:99";
          if (aStart !== bStart) {
            return aStart.localeCompare(bStart);
          }
          return String(a?.title || "").localeCompare(String(b?.title || ""));
        });
      }
      return map;
    },

    waypointCalendarDayCellHtml(dateObj, events, options = {}) {
      const todayKey = toDateKey(new Date());
      const key = toDateKey(dateObj);
      const isToday = key === todayKey;
      const selectedKey = isIsoDate(String(this.waypointSelectedDateKey || "").trim())
        ? String(this.waypointSelectedDateKey || "").trim()
        : toDateKey(this.waypointCalendarDate);
      const isSelected = key === selectedKey;
      const compact = Boolean(options.compact);
      const outside = Boolean(options.outside);
      const limit = compact ? 3 : 8;
      const visible = (events || []).slice(0, limit);
      const extra = (events || []).length - visible.length;

      const classes = ["waypoint-cal-cell"];
      if (isToday) {
        classes.push("is-today");
      }
      if (isSelected) {
        // Keep `is-cursor` for backward-compatible selectors and add explicit selected state.
        classes.push("is-cursor", "is-selected");
      }
      if (outside) {
        classes.push("is-outside");
      }

      const chips = visible
        .map((row) => {
          const ci = this.waypointEntryColorInfo(row);
          const time = this.waypointEventTimeLabel(row);
          const title = escapeHtml(String(row?.title || "Untitled event"));
          const entryId = escapeHtml(String(row?.source_id || row?.id || "").trim());
          const entrySource = escapeHtml(String(row?.source || "event").trim());
          const dotsHtml = ci.colors
            .slice(0, 4)
            .map((c) => `<span class="waypoint-cal-dot" style="--dot-color:${c}"></span>`)
            .join("");
          const dotStack = `<span class="waypoint-cal-dot-stack">${dotsHtml}</span>`;
          if (compact) {
            return `<div class="waypoint-cal-chip is-compact" data-entry-id="${entryId}" data-entry-source="${entrySource}" style="--event-color:${ci.borderColor}">${dotStack}<span class="waypoint-cal-chip-title">${title}</span></div>`;
          }
          const timeHtml = time ? `<span class="waypoint-cal-chip-time">${escapeHtml(time)}</span>` : "";
          return `<div class="waypoint-cal-chip" data-entry-id="${entryId}" data-entry-source="${entrySource}" style="--event-color:${ci.borderColor}">${timeHtml}<span class="waypoint-cal-chip-title">${title}</span>${dotStack}</div>`;
        })
        .join("");

      const extraHtml = extra > 0 ? `<div class="waypoint-cal-more">+${escapeHtml(String(extra))} more</div>` : "";
      return `
        <article class="${classes.join(" ")}" data-cal-date="${key}">
          <header class="waypoint-cal-cell-head">
            <span class="waypoint-cal-daynum">${escapeHtml(String(dateObj.getDate()))}</span>
          </header>
          <div class="waypoint-cal-events">${chips || '<div class="waypoint-cal-empty">No events</div>'}${extraHtml}</div>
        </article>
      `;
    },

    renderWaypointMonthCalendar(anchorDate, eventIndex) {
      const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const dowHtml = dayNames.map((n) => `<div class="waypoint-cal-dow">${n}</div>`).join("");
      const parts = [];
      for (let offset = PLANNER_MONTH_VIEW_PAST_OFFSET; offset <= PLANNER_MONTH_VIEW_FUTURE_OFFSET; offset++) {
        const monthDate = addMonths(anchorDate, offset);
        const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
        const gridStart = startOfWeek(firstOfMonth);
        const monthKey = toDateKey(firstOfMonth).slice(0, 7);
        const monthLabel = escapeHtml(
          monthDate.toLocaleDateString(undefined, { month: "long", year: "numeric" })
        );
        let weeksHtml = "";
        for (let week = 0; week < 6; week++) {
          let cells = "";
          for (let d = 0; d < 7; d++) {
            const day = addDays(gridStart, week * 7 + d);
            const key = toDateKey(day);
            cells += this.waypointCalendarDayCellHtml(day, eventIndex[key] || [], {
              compact: true,
              outside: day.getMonth() !== firstOfMonth.getMonth(),
            });
          }
          weeksHtml += `<div class="waypoint-cal-week-row">${cells}</div>`;
        }
        parts.push(
          `<div class="waypoint-cal-month-block" data-month="${monthKey}">` +
            `<div class="waypoint-cal-month-label">${monthLabel}</div>` +
            `<div class="waypoint-cal-dow-row">${dowHtml}</div>` +
            weeksHtml +
          `</div>`
        );
      }
      return parts.join("");
    },

    renderWaypointThreeDayCalendar(anchorDate, eventIndex) {
      const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const parts = [];
      for (let i = 0; i < 3; i += 1) {
        const day = addDays(anchorDate, i);
        parts.push(`<div class="waypoint-cal-dow">${dayNames[day.getDay()]}</div>`);
      }
      for (let i = 0; i < 3; i += 1) {
        const day = addDays(anchorDate, i);
        const key = toDateKey(day);
        parts.push(this.waypointCalendarDayCellHtml(day, eventIndex[key] || [], { compact: false, outside: false }));
      }
      return `<section class="waypoint-three-day-grid">${parts.join("")}</section>`;
    },

    renderWaypointDayCalendar(anchorDate, eventIndex) {
      const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const key = toDateKey(anchorDate);
      const parts = [
        `<div class="waypoint-cal-dow">${dayNames[anchorDate.getDay()]}</div>`,
        this.waypointCalendarDayCellHtml(anchorDate, eventIndex[key] || [], {
          compact: false,
          outside: false,
        }),
      ];
      return `<section class="waypoint-day-grid">${parts.join("")}</section>`;
    },

    renderWaypointAgendaCalendar(anchorDate, eventIndex) {
      const rows = [];
      for (let i = 0; i < 21; i += 1) {
        const day = addDays(anchorDate, i);
        const key = toDateKey(day);
        const items = Array.isArray(eventIndex[key]) ? eventIndex[key] : [];
        if (!items.length) {
          continue;
        }
        const label = day.toLocaleDateString(undefined, {
          weekday: "short",
          month: "short",
          day: "numeric",
        });
        const itemHtml = items
          .map((row) => {
            const ci = this.waypointEntryColorInfo(row);
            const splitBg = this.waypointEntrySplitBg(ci);
            const agendaStyle = `--event-color:${ci.borderColor}; background:${splitBg};`;
            const time = this.waypointEventTimeLabel(row);
            const title = escapeHtml(String(row?.title || "Untitled"));
            const timeHtml = time ? `<span class="waypoint-agenda-time">${escapeHtml(time)}</span>` : "";
            return `<li class="waypoint-agenda-item" style="${agendaStyle}">${timeHtml}<span class="waypoint-agenda-title">${title}</span></li>`;
          })
          .join("");
        rows.push(
          `<article class="waypoint-agenda-day" data-cal-date="${key}">
            <header>${escapeHtml(label)}</header>
            <ul>${itemHtml}</ul>
          </article>`
        );
      }
      if (!rows.length) {
        return '<section class="waypoint-agenda"><div class="waypoint-cal-empty">No upcoming items.</div></section>';
      }
      return `<section class="waypoint-agenda">${rows.join("")}</section>`;
    },

    renderWaypointCalendar(events) {
      const anchor = startOfLocalDay(this.waypointCalendarDate);
      this.waypointCalendarDate = anchor;
      const view =
        this.waypointCalendarView === "agenda" ||
        this.waypointCalendarView === "day" ||
        this.waypointCalendarView === "three_day" ||
        this.waypointCalendarView === "month"
          ? this.waypointCalendarView
          : "month";
      const eventIndex = this.buildWaypointEventIndex(events || []);
      let html = "";
      let label = "";

      if (view === "month") {
        html = this.renderWaypointMonthCalendar(anchor, eventIndex);
        label = anchor.toLocaleDateString(undefined, { month: "long", year: "numeric" });
      } else if (view === "day") {
        html = this.renderWaypointDayCalendar(anchor, eventIndex);
        label = anchor.toLocaleDateString(undefined, {
          weekday: "long",
          month: "long",
          day: "numeric",
          year: "numeric",
        });
      } else if (view === "three_day") {
        html = this.renderWaypointThreeDayCalendar(anchor, eventIndex);
        const end = addDays(anchor, 2);
        label = `${anchor.toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })} - ${end.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
      } else {
        html = this.renderWaypointAgendaCalendar(anchor, eventIndex);
        label = `Agenda from ${anchor.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
      }

      this.waypointCalendarLabel = label;
      this.waypointCalendarHtml = html;
      if (view === "month") {
        const monthKey = toDateKey(anchor).slice(0, 7);
        this.$nextTick(() => {
          const grid = this.$refs.waypointCalendarGrid;
          if (!grid) return;
          const block = grid.querySelector(`[data-month="${monthKey}"]`);
          if (block) {
            grid.scrollTop = block.offsetTop;
          }
        });
      }
      if (!this.waypointCanShowMonthPreview) {
        this.waypointMonthPreviewOpen = false;
      }
      if (!this.waypointEventForm.date) {
        this.waypointEventForm.date = toDateKey(anchor);
      }
      if (!isIsoDate(String(this.waypointSelectedDateKey || ""))) {
        this.waypointSelectedDateKey = toDateKey(anchor);
      }
    },

    moveWaypointCalendar(direction) {
      this.closeWaypointCalendarMemberFilter();
      const anchor = startOfLocalDay(this.waypointCalendarDate);
      if (this.waypointCalendarView === "agenda") {
        this.waypointCalendarDate = addDays(anchor, Number(direction || 0) * 7);
      } else if (this.waypointCalendarView === "day") {
        this.waypointCalendarDate = addDays(anchor, Number(direction || 0));
      } else if (this.waypointCalendarView === "three_day") {
        this.waypointCalendarDate = addDays(anchor, Number(direction || 0) * 3);
      } else {
        this.waypointCalendarDate = addMonths(anchor, Number(direction || 0));
      }
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    setWaypointCalendarView(view) {
      const nextView = String(view || "").trim().toLowerCase();
      if (!["month", "three_day", "day", "agenda"].includes(nextView)) {
        return;
      }
      this.closeWaypointCalendarMemberFilter();
      this.waypointCalendarView = nextView;
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    setWaypointTypeFilter(type) {
      this.waypointCalendarTypeFilter = String(type || "both").trim();
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    setWaypointCalendarToday() {
      this.closeWaypointCalendarMemberFilter();
      this.waypointCalendarDate = startOfLocalDay(new Date());
      this.waypointSelectedDateKey = toDateKey(this.waypointCalendarDate);
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    onWaypointCalScroll() {
      if (this.waypointCalendarView !== "month") return;
      const grid = this.$refs.waypointCalendarGrid;
      if (!grid) return;
      const scrollTop = grid.scrollTop;
      const blocks = grid.querySelectorAll("[data-month]");
      let activeMonth = null;
      for (const block of blocks) {
        if (block.offsetTop <= scrollTop + 60) {
          activeMonth = block.getAttribute("data-month");
        } else {
          break;
        }
      }
      if (activeMonth && activeMonth !== this._waypointScrollMonth) {
        this._waypointScrollMonth = activeMonth;
        const parts = activeMonth.split("-");
        const d = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
        this.waypointCalendarLabel = d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
        this.waypointCalendarDate = d;
      }
    },

    onWaypointCalendarClick(event) {
      const el = event.target instanceof Element ? event.target : null;
      const chip = el ? el.closest("[data-entry-id]") : null;
      // Chip OR cell: both select the day and reveal the snapshot below — no edit modal
      const target = chip
        ? chip.closest("[data-cal-date]")
        : (el ? el.closest("[data-cal-date]") : null);
      if (!target) return;
      const dateKey = target.getAttribute("data-cal-date") || "";
      const parsed = parseDateKey(dateKey);
      if (!parsed) return;
      this.waypointCalendarDate = parsed;
      this.waypointSelectedDateKey = dateKey;
      this.waypointEventForm.date = dateKey;
      this.waypointDayPanelExpanded = true;
      this.renderWaypointCalendar(this.waypointCalendarEntries());
    },

    openWaypointEntryEdit(row) {
      const source = String(row?.source || "").trim().toLowerCase();
      const srcId = String(row?.source_id || row?.id || "").trim();
      if (source === "task") {
        const task = (this.waypoint?.tasks || []).find((t) => String(t?.id || "").trim() === srcId);
        if (task) this.openWaypointTaskEditModal(task);
      } else {
        const ev = (this.waypoint?.events || []).find(
          (e) => String(e?.id || "").trim() === srcId || String(e?.id || "").trim() === String(row?.id || "").trim()
        );
        if (ev) this.openWaypointEventEditModal(ev);
      }
    },

    openWaypointEntryEditById(entryId, entrySource) {
      const id = String(entryId || "").trim();
      const source = String(entrySource || "").trim().toLowerCase();
      if (source === "task") {
        const task = (this.waypoint?.tasks || []).find((t) => String(t?.id || "").trim() === id);
        if (task) this.openWaypointTaskEditModal(task);
      } else {
        const ev = (this.waypoint?.events || []).find((e) => String(e?.id || "").trim() === id);
        if (ev) this.openWaypointEventEditModal(ev);
      }
    },

    // ── Swipe gesture system ─────────────────────────────────────────────────
    onSwipeTouchStart(e, rowKey) {
      if (!e.touches || e.touches.length !== 1) return;
      const touch = e.touches[0];
      // Skip OS-level edge zones (iOS back/forward swipe ~20px from screen edge)
      if (touch.clientX < 22 || touch.clientX > window.innerWidth - 22) return;
      // Close any already-open row
      if (Object.keys(this.swipeOpen).length) {
        this.swipeOpen = {};
      }
      this._swipeState = {
        rowKey,
        startX: touch.clientX,
        startY: touch.clientY,
        lastX: touch.clientX,
        isHorizontal: null,
        el: null,
      };
    },

    _onGlobalSwipeMove(e) {
      this._onGlobalSidebarSwipeMove(e);
      if (!this._swipeState) return;
      if (!e.touches || e.touches.length !== 1) {
        this._swipeState = null;
        return;
      }
      const touch = e.touches[0];
      const dx = touch.clientX - this._swipeState.startX;
      const dy = touch.clientY - this._swipeState.startY;
      if (this._swipeState.isHorizontal === null) {
        if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        this._swipeState.isHorizontal = Math.abs(dx) > Math.abs(dy);
        if (!this._swipeState.isHorizontal) {
          this._swipeState = null;
          return;
        }
      }
      // Prevent Safari from claiming the swipe for back/forward navigation
      e.preventDefault();
      this._swipeState.lastX = touch.clientX;
      if (!this._swipeState.el) {
        const rk = this._swipeState.rowKey;
        const rowEl = document.querySelector(`[data-swipe-key="${rk.replace(/"/g, '\\"')}"]`);
        this._swipeState.el = rowEl ? rowEl.querySelector(".swipe-content") : null;
      }
      const contentEl = this._swipeState.el;
      if (contentEl) {
        const maxReveal = 124;
        const clamped = Math.max(-maxReveal, Math.min(maxReveal, dx));
        contentEl.style.transition = "none";
        contentEl.style.transform = `translateX(${clamped}px)`;
      }
    },

    onSwipeTouchEnd(e, rowKey) {
      if (!this._swipeState || this._swipeState.rowKey !== rowKey) {
        this._swipeState = null;
        return;
      }
      const state = this._swipeState;
      this._swipeState = null;
      if (!state.isHorizontal) return;
      const dx = state.lastX - state.startX;
      const contentEl = state.el;
      if (contentEl) {
        contentEl.style.transition = "";
        contentEl.style.transform = "";
      }
      const THRESHOLD = window.innerWidth <= 720 ? 52 : 64;
      const newOpen = {};
      if (dx < -THRESHOLD) {
        newOpen[rowKey] = "l"; // swiped left → left-action revealed
      } else if (dx > THRESHOLD) {
        newOpen[rowKey] = "r"; // swiped right → right-action revealed
      }
      this.swipeOpen = newOpen;
    },

    _onGlobalSidebarTouchStart(e) {
      if (!this.isMobileLayout()) {
        this._sidebarSwipeState = null;
        return;
      }
      if (!e.touches || e.touches.length !== 1) {
        this._sidebarSwipeState = null;
        return;
      }
      const target = e.target instanceof Element ? e.target : null;
      if (!target) {
        this._sidebarSwipeState = null;
        return;
      }
      if (
        this.mdOverlayOpen ||
        this.actionsOverlayOpen ||
        this.panelOverlayOpen ||
        this.imageToolStyleModalOpen ||
        this.imageToolPromptModalOpen ||
        this.agentGraphModalOpen ||
        this.familyProfileModalOpen ||
        this.webPushModalOpen ||
        this.projectPickerOpen ||
        this.projectBranchModalOpen ||
        this.projectTargetModalOpen ||
        this.projectTopicTypeModalOpen ||
        this.waypointMemberEditorOpen ||
        this.waypointTaskModalOpen ||
        this.waypointEventModalOpen ||
        this.waypointShoppingModalOpen ||
        this.waypointContactModalOpen ||
        this.emailSettingsModalOpen ||
        this.resetModalOpen
      ) {
        this._sidebarSwipeState = null;
        return;
      }
      if (target.closest(".swipe-row")) {
        this._sidebarSwipeState = null;
        return;
      }

      const touch = e.touches[0];
      const startX = touch.clientX;
      const startY = touch.clientY;
      const edgeThreshold = 28;
      const centerStartThreshold = Math.min(Math.max(160, Math.round(window.innerWidth * 0.58)), 420);
      let mode = "";

      if (!this.sidebarOpen) {
        const canOpenFromContent =
          Boolean(target.closest(".messages")) ||
          Boolean(target.closest(".chat-main")) ||
          Boolean(target.closest(".chat-view")) ||
          Boolean(target.closest(".home-view")) ||
          Boolean(target.closest(".waypoint-view"));
        const openStartThreshold = canOpenFromContent ? centerStartThreshold : edgeThreshold;
        if (startX <= openStartThreshold) {
          mode = "open";
        }
      } else {
        const inSidebar = Boolean(target.closest(".sidebar"));
        const inBackdrop = Boolean(target.closest(".sidebar-backdrop"));
        if (inSidebar || inBackdrop) {
          mode = "close";
        }
      }

      if (!mode) {
        this._sidebarSwipeState = null;
        return;
      }

      this._sidebarSwipeState = {
        mode,
        startX,
        startY,
        lastX: startX,
        isHorizontal: null,
      };
    },

    _onGlobalSidebarSwipeMove(e) {
      if (!this._sidebarSwipeState) {
        return;
      }
      if (!e.touches || e.touches.length !== 1) {
        this._sidebarSwipeState = null;
        return;
      }

      const touch = e.touches[0];
      const state = this._sidebarSwipeState;
      const dx = touch.clientX - state.startX;
      const dy = touch.clientY - state.startY;

      if (state.isHorizontal === null) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) {
          return;
        }
        state.isHorizontal = Math.abs(dx) > Math.abs(dy);
        if (!state.isHorizontal) {
          this._sidebarSwipeState = null;
          return;
        }
      }

      state.lastX = touch.clientX;
      e.preventDefault();
    },

    _onGlobalSidebarTouchEnd(e) {
      const state = this._sidebarSwipeState;
      this._sidebarSwipeState = null;
      if (!state || !state.isHorizontal) {
        return;
      }

      let endX = state.lastX;
      if (e.changedTouches && e.changedTouches.length) {
        endX = e.changedTouches[0].clientX;
      }
      const dx = endX - state.startX;
      const threshold = window.innerWidth <= 720 ? 36 : 48;

      if (state.mode === "open" && dx > threshold) {
        this.sidebarOpen = true;
        this.updateBodyClasses();
        return;
      }
      if (state.mode === "close" && dx < -threshold) {
        this.sidebarOpen = false;
        this.updateBodyClasses();
      }
    },

    closeAllSwipeRows() {
      this.swipeOpen = {};
    },

    swipeCompleteOrDeleteEntry(row) {
      this.closeAllSwipeRows();
      const source = String(row?.source || "").trim().toLowerCase();
      const srcId = String(row?.source_id || row?.id || "").trim();
      if (source === "task") {
        this.completeWaypointTask(srcId);
      } else {
        // Defer past the current event loop so the confirm dialog doesn't
        // trigger a ghost click on the underlying .home-daily-item element.
        setTimeout(() => {
          const label = source === "shopping" ? "shopping item" : "event";
          if (!window.confirm(`Delete this ${label}?`)) return;
          if (source === "shopping") {
            this.deleteWaypointShopping(srcId);
          } else {
            this.deleteWaypointEvent(srcId);
          }
        }, 0);
      }
    },

    swipeEditEntry(row) {
      this.closeAllSwipeRows();
      this.openWaypointEntryEdit(row);
    },
    // ── End swipe gesture system ──────────────────────────────────────────────

    openWaypointAddEventFromCalendar() {
      this.openWaypointCapturePanel("event", this.waypointSelectedDateKey);
    },

    openWaypointAddTaskFromCalendar() {
      this.openWaypointCapturePanel("task", this.waypointSelectedDateKey);
    },

    openWaypointAddShoppingFromCalendar() {
      this.openWaypointCapturePanel("shopping", this.waypointSelectedDateKey);
    },

    openWaypointSmartAddFromCalendar() {
      this.waypointTopTab = "calendar";
      this.waypointBuilderOpen = true;
      this.$nextTick(() => {
        const node = this.$refs.waypointInput;
        if (node && typeof node.focus === "function") {
          node.focus();
        }
      });
    },

    setWaypointState(payload) {
      const next = payload && typeof payload === "object" ? payload : {};
      const normalizeOpenStatus = (value) =>
        String(value || "open").trim().toLowerCase() === "done" ? "done" : "open";
      const normalizeMemberFlag = (value) => {
        if (typeof value === "boolean") {
          return value;
        }
        const text = String(value ?? "").trim().toLowerCase();
        if (!text || text === "false" || text === "0" || text === "no" || text === "n") {
          return false;
        }
        if (text === "true" || text === "1" || text === "yes" || text === "y") {
          return true;
        }
        return Boolean(value);
      };
      const normalizeContactRow = (row) =>
        Object.assign({}, row, {
          is_member: normalizeMemberFlag(row?.is_member),
        });
      const profileColor = this.sanitizeHexColor(
        next.profile_color || this.auth?.profile?.color || this.waypoint?.profile_color || "#4285f4",
        "#4285f4"
      );
      const events = Array.isArray(next.events)
        ? next.events.map((row) => {
            const recurrence = this.normalizeWaypointEventRecurrence(row || {});
            return Object.assign({}, row, {
              color: this.sanitizeHexColor(row?.color || "", profileColor),
              status: normalizeOpenStatus(row?.status),
              member_ids: this.normalizeWaypointMemberIds(row?.member_ids || []),
              member_names: Array.isArray(row?.member_names)
                ? row.member_names.map((x) => String(x || "").trim()).filter(Boolean)
                : [],
              recurrence_enabled: Boolean(recurrence.recurrence_enabled),
              recurrence_type: String(recurrence.recurrence_type || "none"),
              recurrence_interval: Number(recurrence.recurrence_interval || 1),
              recurrence_weekday: Number(recurrence.recurrence_weekday || 0),
              recurrence_day: Number(recurrence.recurrence_day || 1),
              recurrence_nth: Number(recurrence.recurrence_nth || 1),
              recurrence_until: String(recurrence.recurrence_until || ""),
            });
          }).filter((row) => row.status !== "done")
        : [];
      const tasks = Array.isArray(next.tasks)
        ? next.tasks.map((row) =>
            Object.assign({}, row, {
              status: normalizeOpenStatus(row?.status),
              member_ids: this.normalizeWaypointMemberIds(row?.member_ids || []),
              member_names: Array.isArray(row?.member_names)
                ? row.member_names.map((x) => String(x || "").trim()).filter(Boolean)
                : [],
            })
          ).filter((row) => row.status !== "done")
        : [];
      const reminders = Array.isArray(next.reminders)
        ? next.reminders.map((row) =>
            Object.assign({}, row, {
              status: normalizeOpenStatus(row?.status),
            })
          ).filter((row) => row.status !== "done")
        : [];
      const shoppingFood = Array.isArray(next.shopping_food)
        ? next.shopping_food.map((row) =>
            Object.assign({}, row, {
              status: normalizeOpenStatus(row?.status),
            })
          ).filter((row) => row.status !== "done")
        : [];
      const shoppingGeneral = Array.isArray(next.shopping_general)
        ? next.shopping_general.map((row) =>
            Object.assign({}, row, {
              status: normalizeOpenStatus(row?.status),
            })
          ).filter((row) => row.status !== "done")
        : [];
      const contacts = Array.isArray(next.contacts) ? next.contacts.map((row) => normalizeContactRow(row)) : [];
      const payloadMembers = Array.isArray(next.members) ? next.members.map((row) => normalizeContactRow(row)) : [];
      const members = payloadMembers.length ? payloadMembers.filter((row) => row.is_member) : contacts.filter((row) => row.is_member);
      const memberIdSet = new Set(
        members
          .map((row) => String(row?.id || "").trim())
          .filter(Boolean)
      );
      const contactLocations = Array.isArray(next.contact_locations)
        ? next.contact_locations.map((row) =>
            Object.assign({}, row, {
              is_member: normalizeMemberFlag(row?.is_member),
            })
          )
        : [];
      const eventPatterns = Array.isArray(next.event_patterns)
        ? next.event_patterns.map((row) => Object.assign({}, row))
        : [];
      const normalizeInsightAction = (action) =>
        action && typeof action === "object"
          ? {
              id: String(action?.id || "").trim(),
              kind: String(action?.kind || "").trim().toLowerCase(),
              label: String(action?.label || "").trim(),
              title: String(action?.title || "").trim(),
              due_date: String(action?.due_date || "").trim(),
              notes: String(action?.notes || "").trim(),
              priority: String(action?.priority || "medium").trim().toLowerCase() || "medium",
              list_name: String(action?.list_name || "general").trim().toLowerCase() || "general",
              location: String(action?.location || "").trim(),
              related_event_id: String(action?.related_event_id || "").trim(),
              member_ids: Array.isArray(action?.member_ids)
                ? action.member_ids.map((x) => String(x || "").trim()).filter(Boolean)
                : [],
              member_names: Array.isArray(action?.member_names)
                ? action.member_names.map((x) => String(x || "").trim()).filter(Boolean)
                : [],
            }
          : null;
      const normalizeInsightRow = (row) =>
        Object.assign({}, row, {
          id: String(row?.id || "").trim(),
          severity: String(row?.severity || "info").trim().toLowerCase() || "info",
          title: String(row?.title || "").trim(),
          text: String(row?.text || "").trim(),
          date: String(row?.date || "").trim(),
          related_ids: Array.isArray(row?.related_ids)
            ? row.related_ids.map((x) => String(x || "").trim()).filter(Boolean)
            : [],
          action: normalizeInsightAction(row?.action),
        });
      const insightPayload = next.insights && typeof next.insights === "object" ? next.insights : {};
      const insights = {
        summary_lines: Array.isArray(insightPayload.summary_lines)
          ? insightPayload.summary_lines.map((x) => String(x || "").trim()).filter(Boolean)
          : [],
        priorities: Array.isArray(insightPayload.priorities) ? insightPayload.priorities.map(normalizeInsightRow) : [],
        watchouts: Array.isArray(insightPayload.watchouts) ? insightPayload.watchouts.map(normalizeInsightRow) : [],
        suggestions: Array.isArray(insightPayload.suggestions) ? insightPayload.suggestions.map(normalizeInsightRow) : [],
        patterns: Array.isArray(insightPayload.patterns) ? insightPayload.patterns.map(normalizeInsightRow) : [],
        conflicts: Array.isArray(insightPayload.conflicts) ? insightPayload.conflicts.map(normalizeInsightRow) : [],
        counts: insightPayload.counts && typeof insightPayload.counts === "object" ? Object.assign({}, insightPayload.counts) : {},
        week_window: insightPayload.week_window && typeof insightPayload.week_window === "object" ? Object.assign({}, insightPayload.week_window) : {},
      };
      this.waypoint = {
        thread_id: String(next.thread_id || this.waypoint.thread_id || "waypoint_main"),
        messages: Array.isArray(next.messages) ? next.messages : [],
        tasks,
        reminders,
        events,
        event_patterns: eventPatterns,
        insights,
        shopping_food: shoppingFood,
        shopping_general: shoppingGeneral,
        contacts,
        members,
        contact_locations: contactLocations,
        open_tasks_count: Number(next.open_tasks_count || 0),
        open_reminders_count: Number(next.open_reminders_count || 0),
        profile_color: profileColor,
      };
      this.waypointCalendarFilteredMemberIds = this.normalizeWaypointMemberIds(this.waypointCalendarFilteredMemberIds || []).filter((id) =>
        memberIdSet.has(id)
      );
      if (!isIsoDate(String(this.waypointSelectedDateKey || ""))) {
        this.waypointSelectedDateKey = toDateKey(this.waypointCalendarDate);
      }
      this.renderWaypointCalendar(this.waypointCalendarEntries());
      this.$nextTick(() => this.scrollWaypointMessages());
    },

    async refreshWaypointState() {
      this.waypointLoaded = false;
      this.purchaseRecos = [];
    },

    async fetchPurchaseRecos() {
      this.purchaseRecos = [];
    },

    addRecommendedShoppingItem(reco) {
      this.openWaypointShoppingModal("food");
      this.$nextTick(() => {
        this.waypointShoppingForm.title = String(reco.title || "").trim();
      });
    },

    async submitWaypointTaskForm() {
      const title = String(this.waypointTaskForm.title || "").trim();
      if (!title) {
        window.alert("Task title is required.");
        return;
      }
      this.waypointTaskSubmitting = true;
      try {
        const selectedMemberIds = this.normalizeWaypointMemberIds(this.waypointTaskForm.member_ids || []);
        const body = {
          title,
          due_date: String(this.waypointTaskForm.due_date || "").trim(),
          priority: String(this.waypointTaskForm.priority || "medium").trim() || "medium",
          list_name: String(this.waypointTaskForm.list_name || "general").trim() || "general",
          member_ids: selectedMemberIds,
          location: String(this.waypointTaskForm.location || "").trim(),
          recurrence_enabled: Boolean(this.waypointTaskForm.recurrence_enabled),
          recurrence_type: String(this.waypointTaskForm.recurrence_type || "weekly_day"),
          recurrence_interval: Number(this.waypointTaskForm.recurrence_interval) || 1,
          recurrence_weekday: Number(this.waypointTaskForm.recurrence_weekday) || 0,
          recurrence_day: Number(this.waypointTaskForm.recurrence_day) || 1,
          recurrence_nth: Number(this.waypointTaskForm.recurrence_nth) || 1,
          recurrence_until: String(this.waypointTaskForm.recurrence_until || "").trim(),
        };
        const payload = this.waypointTaskEditId
          ? await this.apiPatch(`/api/waypoint/tasks/${encodeURIComponent(this.waypointTaskEditId)}`, body)
          : await this.apiPost("/api/waypoint/tasks", body);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Failed to save task.");
          return;
        }
        this.waypointTaskForm.title = "";
        this.waypointTaskForm.due_date = "";
        this.waypointTaskForm.member_ids = [];
        this.closeWaypointTaskModal();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Task save failed: ${String(err.message || err)}`);
      } finally {
        this.waypointTaskSubmitting = false;
      }
    },

    async submitWaypointEventForm() {
      const title = String(this.waypointEventForm.title || "").trim();
      const date = String(this.waypointEventForm.date || "").trim();
      if (!title) {
        window.alert("Event title is required.");
        return;
      }
      if (!isIsoDate(date)) {
        window.alert("Event date is required (YYYY-MM-DD).");
        return;
      }

      this.waypointEventSubmitting = true;
      try {
        const hostIds = new Set((this.waypointHostContactLocationOptions || []).map((opt) => String(opt?.value || "").trim()));
        const selectedContactIdRaw = String(this.waypointEventForm.location_contact_id || "").trim();
        const selectedContactId = hostIds.has(selectedContactIdRaw) ? selectedContactIdRaw : "";
        if (!selectedContactId) {
          window.alert("Select a host contact with a saved address.");
          return;
        }
        const selectedMemberIds = this.normalizeWaypointMemberIds(this.waypointEventForm.member_ids || []);
        const reminderTime = normalizeTimeText(this.waypointEventForm.reminder_time || "");
        const notes = reminderTime ? `remind_at=${reminderTime}` : "";
        const body = {
          title,
          date,
          start_time: String(this.waypointEventForm.start_time || "").trim(),
          end_time: String(this.waypointEventForm.end_time || "").trim(),
          notes,
          location_contact_id: selectedContactId,
          member_ids: selectedMemberIds,
          recurrence_enabled: Boolean(this.waypointEventForm.recurrence_enabled),
          recurrence_type: normalizeRecurrenceType(this.waypointEventForm.recurrence_type || "none"),
          recurrence_interval: Math.max(1, Math.min(12, Number.parseInt(this.waypointEventForm.recurrence_interval, 10) || 1)),
          recurrence_weekday: Math.max(0, Math.min(6, Number.parseInt(this.waypointEventForm.recurrence_weekday, 10) || 0)),
          recurrence_day: Math.max(1, Math.min(31, Number.parseInt(this.waypointEventForm.recurrence_day, 10) || 1)),
          recurrence_nth: Math.max(1, Math.min(5, Number.parseInt(this.waypointEventForm.recurrence_nth, 10) || 1)),
          recurrence_until: isIsoDate(String(this.waypointEventForm.recurrence_until || "").trim())
            ? String(this.waypointEventForm.recurrence_until || "").trim()
            : "",
        };
        if (!body.recurrence_enabled) {
          body.recurrence_type = "none";
          body.recurrence_interval = 1;
          body.recurrence_until = "";
        }
        const payload = this.waypointEventEditId
          ? await this.apiPatch(`/api/waypoint/events/${encodeURIComponent(this.waypointEventEditId)}`, body)
          : await this.apiPost("/api/waypoint/events", body);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Failed to save event.");
          return;
        }
        this.waypointCalendarDate = parseDateKey(date) || this.waypointCalendarDate;
        this.renderWaypointCalendar(this.waypointCalendarEntries());
        this.waypointEventForm.title = "";
        this.waypointEventForm.start_time = "";
        this.waypointEventForm.end_time = "";
        this.waypointEventForm.reminder_time = "";
        this.waypointEventForm.location_contact_id = "";
        this.waypointEventForm.location = "";
        this.waypointEventForm.member_ids = [];
        this.waypointEventForm.recurrence_enabled = false;
        this.waypointEventForm.recurrence_type = "weekly_day";
        this.waypointEventForm.recurrence_interval = 1;
        this.waypointEventForm.recurrence_weekday = this.waypointDefaultRecurrenceWeekdayForDate(date);
        this.waypointEventForm.recurrence_day = (parseDateKey(date) || startOfLocalDay(new Date())).getDate();
        this.waypointEventForm.recurrence_nth = this.waypointDefaultRecurrenceNthForDate(date);
        this.waypointEventForm.recurrence_until = "";
        this.closeWaypointEventModal();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Event save failed: ${String(err.message || err)}`);
      } finally {
        this.waypointEventSubmitting = false;
      }
    },

    async submitWaypointShoppingForm() {
      const title = String(this.waypointShoppingForm.title || "").trim();
      if (!title) {
        window.alert("Item title is required.");
        return;
      }

      this.waypointShoppingSubmitting = true;
      try {
        const body = {
          title,
          category: String(this.waypointShoppingForm.category || "food").trim().toLowerCase() || "food",
        };
        const payload = this.waypointShoppingEditId
          ? await this.apiPatch(`/api/waypoint/shopping/${encodeURIComponent(this.waypointShoppingEditId)}`, body)
          : await this.apiPost("/api/waypoint/shopping", body);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Failed to save item.");
          return;
        }
        this.waypointShoppingForm.title = "";
        this.closeWaypointShoppingModal();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Item save failed: ${String(err.message || err)}`);
      } finally {
        this.waypointShoppingSubmitting = false;
      }
    },

    onWaypointEventLocationContactChanged() {
      const contactId = String(this.waypointEventForm.location_contact_id || "").trim();
      if (!contactId) {
        this.waypointEventForm.location = "";
        return;
      }
      const rows = Array.isArray(this.waypoint?.contact_locations) ? this.waypoint.contact_locations : [];
      const row = rows.find((x) => String(x?.id || "").trim() === contactId);
      if (!row) {
        return;
      }
      const location = String(row.location || "").trim();
      if (location) {
        this.waypointEventForm.location = location;
      }
    },

    async submitWaypointContactForm() {
      const name = String(this.waypointContactForm.name || "").trim();
      if (!name) {
        window.alert("Contact name is required.");
        return;
      }
      const locationName = String(this.waypointContactForm.location_name || "").trim();
      const locationAddress = String(this.waypointContactForm.location_address || "").trim();
      if (!locationAddress) {
        window.alert("A saved address is required.");
        return;
      }
      if (!this.isLikelySavedAddress(locationAddress)) {
        window.alert("Use a real street-style address (number + street/city details).");
        return;
      }
      this.waypointContactSubmitting = true;
      try {
        const body = Object.assign({
          name,
          kind: String(this.waypointContactForm.kind || "person").trim().toLowerCase(),
          relationship: String(this.waypointContactForm.relationship || "friend").trim().toLowerCase(),
          location_name: locationName,
          location_address: locationAddress,
        }, this.waypointContactDetailsPayload(this.waypointContactForm));
        const payload = this.waypointContactEditId
          ? await this.apiPatch(`/api/waypoint/contacts/${encodeURIComponent(this.waypointContactEditId)}`, body)
          : await this.apiPost("/api/waypoint/contacts", body);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Failed to save contact.");
          return;
        }
        this.waypointContactForm = blankWaypointContactFormDefaults();
        this.waypointContactDetailsOpen = false;
        this.closeWaypointContactModal();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Contact save failed: ${String(err.message || err)}`);
      } finally {
        this.waypointContactSubmitting = false;
      }
    },

    async submitWaypointMemberForm() {
      const name = String(this.waypointMemberForm.name || "").trim();
      if (!name) {
        window.alert("Member name is required.");
        return;
      }
      const locationName = String(this.waypointMemberForm.location_name || "").trim();
      const locationAddress = String(this.waypointMemberForm.location_address || "").trim();
      if (!locationAddress) {
        window.alert("A saved address is required.");
        return;
      }
      if (!this.isLikelySavedAddress(locationAddress)) {
        window.alert("Use a real street-style address (number + street/city details).");
        return;
      }
      const createLogin = Boolean(this.waypointMemberForm.create_login);
      const username = String(this.waypointMemberForm.username || "").trim();
      const pin = String(this.waypointMemberForm.pin || "").trim();
      if (createLogin && !this.auth?.profile?.is_owner) {
        window.alert("Only owner can create member logins.");
        return;
      }
      if (createLogin && !username) {
        window.alert("Username is required when login is enabled.");
        return;
      }
      if (createLogin && !this.isFourDigitPin(pin)) {
        window.alert("PIN must be exactly 4 digits.");
        return;
      }

      this.waypointMemberSubmitting = true;
      try {
        const payload = await this.apiPost("/api/waypoint/members", Object.assign({
          name,
          kind: String(this.waypointMemberForm.kind || "person").trim().toLowerCase(),
          relationship: String(this.waypointMemberForm.relationship || "friend").trim().toLowerCase(),
          member_role: String(this.waypointMemberForm.member_role || "adult").trim().toLowerCase(),
          create_login: createLogin,
          username,
          pin,
          color: String(this.waypointMemberForm.color || "").trim(),
          location_name: locationName,
          location_address: locationAddress,
        }, this.waypointContactDetailsPayload(this.waypointMemberForm)));
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Failed to add member.");
          return;
        }
        if (createLogin && payload?.profile) {
          window.alert(
            `Member login created for ${String(payload.profile.display_name || payload.profile.username || name)}.\n` +
              `Username: ${String(payload.profile.username || username)}`
          );
        }
        this.waypointMemberForm = blankWaypointMemberFormDefaults();
      } catch (err) {
        window.alert(`Add member failed: ${String(err.message || err)}`);
      } finally {
        this.waypointMemberSubmitting = false;
      }
    },

    openWaypointMemberEditorAdd() {
      this.closeWaypointEntryModals();
      this.waypointMemberEditorMode = "add";
      this.waypointMemberDeleteConfirm = "";
      this.waypointMemberEditorDetailsOpen = true;
      this.waypointMemberEditorForm = blankWaypointMemberEditorForm(
        this.sanitizeHexColor(this.auth?.profile?.color || "#4285f4", "#4285f4")
      );
      this.waypointMemberEditorSubmitting = false;
      this.waypointMemberEditorOpen = true;
      this.updateBodyClasses();
    },

    openWaypointMemberEditorEdit(person) {
      const row = person && typeof person === "object" ? person : {};
      this.closeWaypointEntryModals();
      this.waypointMemberEditorMode = "edit";
      this.waypointMemberDeleteConfirm = "";
      const color = this.sanitizeHexColor(row.color || this.auth?.profile?.color || "#4285f4", "#4285f4");
      this.waypointMemberEditorForm = Object.assign(blankWaypointMemberEditorForm(color), {
        id: String(row.id || "").trim(),
        name: String(row.name || "").trim(),
        kind: String(row.kind || "person").trim().toLowerCase() || "person",
        relationship: String(row.relationship || "friend").trim().toLowerCase() || "friend",
        member_role: String(row.member_role || "adult").trim().toLowerCase() || "adult",
        create_login: false,
        profile_user_id: String(row.profile_user_id || "").trim(),
        username: String(row.username || "").trim(),
        pin: "",
        color,
        location_name: String(row.location_name || "").trim(),
        location_address: String(row.location_address || "").trim(),
        notes: String(row.notes || "").trim(),
        nickname: String(row.nickname || "").trim(),
        birthday: String(row.birthday || "").trim(),
        age: String(row.age || "").trim(),
        age_is_estimate: Boolean(row.age_is_estimate),
        gender: String(row.gender || "").trim(),
        school_or_work: String(row.school_or_work || "").trim(),
        likes: String(row.likes || "").trim(),
        dislikes: String(row.dislikes || "").trim(),
        important_dates: String(row.important_dates || "").trim(),
        medical_notes: String(row.medical_notes || "").trim(),
        email: String(row.email || "").trim(),
        phone: String(row.phone || "").trim(),
      });
      if (String(this.waypointMemberEditorForm.birthday || "").trim()) {
        this.waypointMemberEditorForm.age = "";
        this.waypointMemberEditorForm.age_is_estimate = false;
      }
      this.waypointMemberEditorDetailsOpen = true;
      this.waypointMemberEditorSubmitting = false;
      this.waypointMemberEditorOpen = true;
      this.updateBodyClasses();
    },

    closeWaypointMemberEditor() {
      this.waypointMemberEditorOpen = false;
      this.waypointMemberEditorSubmitting = false;
      this.waypointMemberDeleteConfirm = "";
      this.waypointMemberEditorDetailsOpen = false;
      this.updateBodyClasses();
    },

    async submitWaypointMemberEditor() {
      const name = String(this.waypointMemberEditorForm.name || "").trim();
      if (!name) {
        window.alert("Member name is required.");
        return;
      }
      const color = this.sanitizeHexColor(this.waypointMemberEditorForm.color || "#4285f4", "#4285f4");
      const username = String(this.waypointMemberEditorForm.username || "").trim();
      const pin = String(this.waypointMemberEditorForm.pin || "").trim();
      const wantsLogin = Boolean(this.waypointMemberEditorForm.create_login);
      const hasProfile = Boolean(String(this.waypointMemberEditorForm.profile_user_id || "").trim());
      if (wantsLogin && !this.auth?.profile?.is_owner) {
        window.alert("Only owner can create member logins.");
        return;
      }
      if ((wantsLogin || hasProfile) && pin && !this.isFourDigitPin(pin)) {
        window.alert("PIN must be exactly 4 digits.");
        return;
      }
      if (wantsLogin && !username) {
        window.alert("Username is required when creating login.");
        return;
      }
      const locationName = String(this.waypointMemberEditorForm.location_name || "").trim();
      const locationAddress = String(this.waypointMemberEditorForm.location_address || "").trim();
      if (!locationAddress) {
        window.alert("A saved address is required.");
        return;
      }
      if (!this.isLikelySavedAddress(locationAddress)) {
        window.alert("Use a real street-style address (number + street/city details).");
        return;
      }
      const detailsPayload = this.waypointContactDetailsPayload(this.waypointMemberEditorForm);

      this.waypointMemberEditorSubmitting = true;
      try {
        if (this.waypointMemberEditorMode === "add") {
          const payload = await this.apiPost("/api/waypoint/members", Object.assign({
            name,
            kind: String(this.waypointMemberEditorForm.kind || "person").trim().toLowerCase(),
            relationship: String(this.waypointMemberEditorForm.relationship || "friend").trim().toLowerCase(),
            member_role: String(this.waypointMemberEditorForm.member_role || "adult").trim().toLowerCase(),
            create_login: wantsLogin,
            username,
            pin,
            color,
            location_name: locationName,
            location_address: locationAddress,
          }, detailsPayload));
          if (payload?.state) {
            this.setWaypointState(payload.state);
          }
          if (payload?.ok === false) {
            window.alert(payload.message || "Failed to add member.");
            return;
          }
        } else {
          const contactId = String(this.waypointMemberEditorForm.id || "").trim();
          if (!contactId) {
            window.alert("Missing member id.");
            return;
          }
          const payload = await this.apiPatch(`/api/waypoint/contacts/${encodeURIComponent(contactId)}`, Object.assign({
            name,
            kind: String(this.waypointMemberEditorForm.kind || "person").trim().toLowerCase(),
            relationship: String(this.waypointMemberEditorForm.relationship || "friend").trim().toLowerCase(),
            member_role: String(this.waypointMemberEditorForm.member_role || "adult").trim().toLowerCase(),
            location_name: locationName,
            location_address: locationAddress,
            color,
            username,
            profile_user_id: String(this.waypointMemberEditorForm.profile_user_id || "").trim(),
            create_login: wantsLogin,
            sync_profile: hasProfile || wantsLogin,
            pin,
          }, detailsPayload));
          if (payload?.state) {
            this.setWaypointState(payload.state);
          }
          if (payload?.ok === false) {
            window.alert(payload.message || "Failed to update member.");
            return;
          }
        }
        this.closeWaypointMemberEditor();
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Member save failed: ${String(err.message || err)}`);
      } finally {
        this.waypointMemberEditorSubmitting = false;
      }
    },

    async deleteWaypointContact(contactId, options = {}) {
      const id = String(contactId || "").trim();
      if (!id) {
        return false;
      }
      const closeModals = options && options.closeModals !== false;
      try {
        const payload = await this.apiDelete(`/api/waypoint/contacts/${encodeURIComponent(id)}`);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Contact delete failed.");
          return false;
        }
        if (closeModals) {
          this.closeWaypointContactModal();
          this.closeWaypointMemberEditor();
        }
        await this.refreshPanelBadges();
        return true;
      } catch (err) {
        window.alert(`Contact delete failed: ${String(err.message || err)}`);
        return false;
      }
    },

    async deleteWaypointContactFromModal() {
      const contactId = String(this.waypointContactEditId || "").trim();
      if (!contactId) {
        return;
      }
      if (!this.canHardDelete(this.waypointContactDeleteConfirm)) {
        window.alert('Type "YES I AM SURE" exactly to delete this contact.');
        return;
      }
      this.waypointContactSubmitting = true;
      try {
        await this.deleteWaypointContact(contactId);
      } finally {
        this.waypointContactSubmitting = false;
      }
    },

    async deleteWaypointMemberFromModal() {
      const contactId = String(this.waypointMemberEditorForm?.id || "").trim();
      if (!contactId) {
        return;
      }
      if (!this.canHardDelete(this.waypointMemberDeleteConfirm)) {
        window.alert('Type "YES I AM SURE" exactly to delete this member.');
        return;
      }
      this.waypointMemberEditorSubmitting = true;
      try {
        await this.deleteWaypointContact(contactId);
      } finally {
        this.waypointMemberEditorSubmitting = false;
      }
    },

    toggleWaypointBuilder() {
      this.waypointBuilderOpen = !this.waypointBuilderOpen;
      if (this.waypointBuilderOpen) {
        if (!String(this.waypointBuilder.shopping_items || "").trim() && String(this.waypointBuilder.shopping_item || "").trim()) {
          this.waypointBuilder.shopping_items = String(this.waypointBuilder.shopping_item || "").trim();
        }
        this.$nextTick(() => {
          const root = this.$refs.waypointBuilderMenu;
          if (root && root.querySelector) {
            const firstInput = root.querySelector("select, input, textarea");
            if (firstInput && typeof firstInput.focus === "function") {
              firstInput.focus();
            }
          }
        });
      }
    },

    buildWaypointCommandFromBuilder() {
      const cmd = String(this.waypointBuilder?.command || "").trim();
      if (!cmd) {
        return "";
      }

      if (cmd === "shopping_add") {
        const items = this.parseWaypointBuilderItems(
          this.waypointBuilder.shopping_items || this.waypointBuilder.shopping_item || ""
        );
        const category = String(this.waypointBuilder.shopping_category || "food").trim().toLowerCase();
        if (!items.length) {
          return "";
        }
        return `add shopping ${category === "general" ? "general" : "food"} ${items.join(", ")}`;
      }

      if (cmd === "shopping_complete") {
        const itemId = String(this.waypointBuilder.shopping_id || "").trim();
        return itemId ? `bought ${itemId}` : "";
      }

      if (cmd === "shopping_delete") {
        const itemId = String(this.waypointBuilder.shopping_id || "").trim();
        return itemId ? `delete shopping ${itemId}` : "";
      }

      if (cmd === "task_add") {
        const title = String(this.waypointBuilder.task_title || "").trim();
        if (!title) {
          return "";
        }
        let command = `add task ${title}`;
        const dueDate = String(this.waypointBuilder.task_due_date || "").trim();
        if (isIsoDate(dueDate)) {
          command += ` due ${dueDate}`;
        }
        const priority = String(this.waypointBuilder.task_priority || "medium").trim().toLowerCase();
        if (["high", "medium", "low"].includes(priority)) {
          command += ` priority ${priority}`;
        }
        return command;
      }

      if (cmd === "task_complete") {
        const taskId = String(this.waypointBuilder.task_id || "").trim();
        return taskId ? `done ${taskId}` : "";
      }

      if (cmd === "task_blocked") {
        const taskId = String(this.waypointBuilder.task_id || "").trim();
        const reason = String(this.waypointBuilder.task_reason || "").trim();
        if (!taskId || !reason) {
          return "";
        }
        return `not done ${taskId} because ${reason}`;
      }

      if (cmd === "event_add") {
        const title = String(this.waypointBuilder.event_title || "").trim();
        const date = String(this.waypointBuilder.event_date || "").trim();
        if (!title || !isIsoDate(date)) {
          return "";
        }
        let command = `add event ${title} on ${date}`;
        const start = normalizeTimeText(this.waypointBuilder.event_start || "");
        const end = normalizeTimeText(this.waypointBuilder.event_end || "");
        if (start) {
          command += ` at ${start}`;
          if (end) {
            command += ` to ${end}`;
          }
        } else if (end) {
          command += ` to ${end}`;
        }
        const locationContactId = String(this.waypointBuilder.event_location_contact_id || "").trim();
        if (!locationContactId) {
          return "";
        }
        command += ` location:contact:${locationContactId}`;
        return command;
      }

      if (cmd === "event_delete") {
        const eventId = String(this.waypointBuilder.event_id || "").trim();
        return eventId ? `delete event ${eventId}` : "";
      }

      if (cmd === "show_tasks") {
        return "show tasks";
      }
      if (cmd === "show_contacts") {
        return "show contacts";
      }
      if (cmd === "show_members") {
        return "show members";
      }
      if (cmd === "show_reminders") {
        return "show reminders";
      }
      if (cmd === "show_shopping") {
        return "show shopping";
      }
      if (cmd === "show_events") {
        return "show events";
      }
      if (cmd === "summary") {
        return "summary";
      }
      if (cmd === "help") {
        return "help";
      }
      return "";
    },

    async applyWaypointBuilder(sendNow) {
      const command = this.buildWaypointCommandFromBuilder();
      if (!command) {
        window.alert("Complete required fields first.");
        return;
      }
      if (sendNow) {
        this.waypointDraft = command;
        this.resizeWaypointComposer();
        this.waypointBuilderOpen = false;
        await this.sendWaypointMessage();
        return;
      }
      const current = String(this.waypointDraft || "").trim();
      this.waypointDraft = current ? `${current}\n${command}` : command;
      this.resizeWaypointComposer();
      this.$nextTick(() => {
        const node = this.$refs.waypointInput;
        if (node) {
          node.focus();
        }
      });
    },

    async sendWaypointMessage() {
      const text = String(this.waypointDraft || "").trim();
      if (!text || this.waypointSending) {
        return;
      }
      this.waypointBuilderOpen = false;
      this.waypointSending = true;
      this.waypointDraft = "";
      this.resizeWaypointComposer();
      try {
        const payload = await this.apiPost("/api/waypoint/messages", {
          content: text,
          project: this.activeProject,
        });
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        await this.refreshPanelBadges();
      } catch (err) {
        const nextMessages = Array.isArray(this.waypoint?.messages) ? this.waypoint.messages.slice() : [];
        nextMessages.push({
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `Error: ${String(err.message || err)}`,
          ts: new Date().toISOString(),
        });
        this.waypoint = Object.assign({}, this.waypoint, { messages: nextMessages });
      } finally {
        this.waypointSending = false;
        this.$nextTick(() => this.scrollWaypointMessages());
      }
    },

    async applyWaypointInsightAction(actionId) {
      const target = String(actionId || "").trim();
      if (!target || this.waypointInsightBusy[target]) {
        return;
      }
      this.waypointInsightBusy = Object.assign({}, this.waypointInsightBusy, { [target]: true });
      try {
        const payload = await this.apiPost("/api/waypoint/insights/apply", {
          action_id: target,
          project: this.activeProject,
        });
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Insight action failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Waypoints insight action failed: ${String(err.message || err)}`);
      } finally {
        const nextBusy = Object.assign({}, this.waypointInsightBusy);
        delete nextBusy[target];
        this.waypointInsightBusy = nextBusy;
      }
    },

    async completeWaypointTask(taskId) {
      if (!taskId) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/waypoint/tasks/${encodeURIComponent(taskId)}/complete`, {});
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Task completion failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Waypoints task action failed: ${String(err.message || err)}`);
      }
    },

    openTaskReminderDialog(task) {
      this.showWaypointRetiredNotice();
    },

    closeTaskReminderDialog() {
      return;
    },

    setTaskReminderFromNow(minutes) {
      return;
    },

    setTaskReminderCustomMinutes() {
      return;
    },

    syncTaskReminderSliderFromTime() {
      return;
    },

    syncTaskReminderTimeFromSlider() {
      return;
    },

    async applyTaskReminder() {
      this.showWaypointRetiredNotice();
    },

    async snoozeWaypointTask(taskId) {
      this.showWaypointRetiredNotice();
    },

    async deleteWaypointTask(taskId) {
      if (!taskId) {
        return;
      }
      if (!window.confirm("Delete this task?")) {
        return;
      }
      try {
        const payload = await this.apiDelete(`/api/waypoint/tasks/${encodeURIComponent(taskId)}`);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Task delete failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Waypoints task delete failed: ${String(err.message || err)}`);
      }
    },

    async deleteWaypointEvent(eventId) {
      if (!eventId) {
        return;
      }
      if (!window.confirm("Delete this event?")) {
        return;
      }
      try {
        const payload = await this.apiDelete(`/api/waypoint/events/${encodeURIComponent(eventId)}`);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Event delete failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Waypoints event delete failed: ${String(err.message || err)}`);
      }
    },

    async completeWaypointEvent(eventId) {
      if (!eventId) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/waypoint/events/${encodeURIComponent(eventId)}/complete`, {});
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Event complete failed.");
          return;
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Waypoints event action failed: ${String(err.message || err)}`);
      }
    },

    async completeWaypointShopping(itemId) {
      if (!itemId) {
        return;
      }
      try {
        const payload = await this.apiPost(`/api/waypoint/shopping/${encodeURIComponent(itemId)}/complete`, {});
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Shopping completion failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Shopping action failed: ${String(err.message || err)}`);
      }
    },

    async deleteWaypointShopping(itemId) {
      if (!itemId) {
        return;
      }
      if (!window.confirm("Delete this shopping item?")) {
        return;
      }
      try {
        const payload = await this.apiDelete(`/api/waypoint/shopping/${encodeURIComponent(itemId)}`);
        if (payload?.state) {
          this.setWaypointState(payload.state);
        }
        if (payload?.ok === false) {
          window.alert(payload.message || "Shopping delete failed.");
        }
        await this.refreshPanelBadges();
      } catch (err) {
        window.alert(`Shopping delete failed: ${String(err.message || err)}`);
      }
    },

    scrollMessages() {
      const node = this.$refs.messages;
      if (node) {
        node.scrollTop = node.scrollHeight;
      }
    },

    scrollWaypointMessages() {
      const node = this.$refs.waypointMessages;
      if (node) {
        node.scrollTop = node.scrollHeight;
      }
    },

    resizeComposer() {
      const node = this.$refs.composerInput;
      if (!node) {
        return;
      }
      node.style.height = "auto";
      node.style.height = `${Math.min(node.scrollHeight, 220)}px`;
    },

    resizeWaypointComposer() {
      const node = this.$refs.waypointInput;
      if (!node) {
        return;
      }
      node.style.height = "auto";
      node.style.height = `${Math.min(node.scrollHeight, 180)}px`;
    },

    scrollToMessage(msgId) {
      const id = String(msgId || "").trim();
      if (!id) return;
      const el = document.querySelector(`[data-msg-id="${CSS.escape(id)}"]`);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("msg-highlight-flash");
      setTimeout(() => el.classList.remove("msg-highlight-flash"), 1400);
    },

    onMessagesClick(event) {
      const target = event.target instanceof Element ? event.target.closest(".file-inline-link, .md-inline-link") : null;
      if (!target) {
        return;
      }
      const encoded = target.getAttribute("data-file-path") || target.getAttribute("data-md-path") || "";
      if (!encoded) {
        return;
      }
      this.loadFileOverlay(decodeURIComponent(encoded));
    },

    async loadFileOverlay(path) {
      if (this.activeConversationSending) {
        return;
      }
      this.mdTitle = "Loading file...";
      this.mdPath = path;
      this.mdHtml = '<p class="md-loading">Loading file preview...</p>';
      this.mdOverlayOpen = true;
      this.updateBodyClasses();
      try {
        const payload = await this.apiGet(`/api/files/read?path=${encodeURIComponent(path)}`);
        this.mdTitle = payload.name || "File Preview";
        this.mdPath = payload.path || path;
        const render = String(payload.render || "").trim().toLowerCase();
        if (render === "markdown") {
          this.mdHtml = markdownToHtml(payload.content || "");
        } else if (render === "binary") {
          const ext = String(payload.ext || "").trim() || "(none)";
          const mime = String(payload.mime || "").trim() || "application/octet-stream";
          this.mdHtml = `<p class="md-error">Preview unavailable for binary file type.</p><p class="md-meta">ext: ${escapeHtml(
            ext
          )} | mime: ${escapeHtml(mime)}</p>`;
        } else {
          const text = String(payload.content || "");
          const truncated = Boolean(payload.truncated);
          const body = `<pre><code>${escapeHtml(text)}</code></pre>`;
          const note = truncated ? '<p class="md-meta">Preview truncated to 250 KB.</p>' : "";
          this.mdHtml = `${note}${body}`;
        }
      } catch (err) {
        this.mdTitle = "Unable to open file";
        this.mdHtml = `<p class="md-error">${escapeHtml(String(err.message || err))}</p>`;
      }
    },

    async loadMarkdownOverlay(path) {
      await this.loadFileOverlay(path);
    },

    closeMarkdownOverlay() {
      this.mdOverlayOpen = false;
      this.mdTitle = "File Preview";
      this.mdPath = "";
      this.mdHtml = "";
      this.updateBodyClasses();
    },

    async bootstrapConversations(options = {}) {
      if (this.auth.enabled && !this.auth.authenticated) {
        return;
      }
      const activateApp = options?.activateApp !== false;

      await this.refreshConversations();
      const hashId = location.hash.replace("#", "").trim();
      const hasHash = hashId && this.conversations.some((c) => c.id === hashId);
      if (hasHash) {
        await this.openConversation(hashId, { activateApp });
        return;
      }

      if (this.conversations.length > 0) {
        await this.openConversation(this.conversations[0].id, { activateApp });
        return;
      }

      await this.createConversation("", { activateApp });
    },

    onWindowClick(event) {
      const target = event.target;
      if (!(target instanceof Element)) {
        this.chatMenuOpen = false;
        this.composerAddMenuOpen = false;
        this.waypointBuilderOpen = false;
        this.waypointCalendarMemberFilterOpen = false;
        this.homeWeatherExpanded = false;
        return;
      }
      if (this.chatMenuOpen && !target.closest(".chat-menu-wrap")) {
        this.chatMenuOpen = false;
      }
      if (this.composerAddMenuOpen && !target.closest(".composer-add-menu-wrap")) {
        this.composerAddMenuOpen = false;
      }
      if (this.homeWeatherExpanded && !target.closest(".home-hero-weather")) {
        this.homeWeatherExpanded = false;
      }
      if (this.waypointBuilderOpen && !target.closest(".waypoint-builder-wrap")) {
        this.waypointBuilderOpen = false;
      }
      if (this.waypointCalendarMemberFilterOpen && !target.closest(".waypoint-member-filter")) {
        this.waypointCalendarMemberFilterOpen = false;
      }
      if (Object.keys(this.swipeOpen).length && !target.closest(".swipe-row")) {
        this.swipeOpen = {};
      }
    },

    onKeyDown(event) {
      if (event.key !== "Escape") {
        return;
      }
      this.closeAllOverlays();
    },

    async onHashChange() {
      const id = location.hash.replace("#", "").trim();
      if (!id || (!this.auth.authenticated && this.auth.enabled)) {
        return;
      }
      if (this.activeConversationId === id) {
        return;
      }
      try {
        await this.openConversation(id);
      } catch (_err) {}
    },

    onResize() {
      this.syncViewportHeight();
      this.updateBodyClasses();
      this.resizeComposer();
    },
  },

  async mounted() {
    this.initVoice();
    let storedMode = "talk";
    let storedProject = "general";
    let storedTheme = "Night";
    let storedUsername = "owner";
    try {
      const savedMode = localStorage.getItem("oathweaver_input_mode");
      if (savedMode === "command") {
        storedMode = "make";
      } else if (savedMode === "talk" || savedMode === "forage" || savedMode === "make" || savedMode === "plan") {
        storedMode = savedMode;
      }
      const savedProject = localStorage.getItem("oathweaver_active_project");
      if (savedProject) {
        storedProject = normalizeProjectSlug(savedProject);
      }
      const savedTheme = localStorage.getItem("oathweaver_theme");
      if (savedTheme) {
        storedTheme = savedTheme;
      }
      const savedUsername = localStorage.getItem("oathweaver_login_username");
      if (savedUsername) {
        storedUsername = String(savedUsername).trim() || storedUsername;
      }
    } catch (_err) {}

    this.inputMode = storedMode;
    this.setActiveProject(storedProject);
    this.applyTheme(storedTheme, false);
    await this.applyFontConfig();
    this.loginUsername = storedUsername;
    this.authSetup.username = storedUsername;
    this.syncViewportHeight();
    this.updateBodyClasses();
    this.resizeComposer();

    this._boundWindowClick = this.onWindowClick.bind(this);
    this._boundResize = this.onResize.bind(this);
    this._boundHashChange = this.onHashChange.bind(this);
    this._boundKeydown = this.onKeyDown.bind(this);
    this._boundAgentGraphMouseMove = this.onAgentGraphCanvasMouseMove.bind(this);
    this._boundAgentGraphMouseUp = this.onAgentGraphCanvasMouseUp.bind(this);

    window.addEventListener("click", this._boundWindowClick);
    window.addEventListener("resize", this._boundResize);
    window.addEventListener("orientationchange", this._boundResize);
    window.addEventListener("hashchange", this._boundHashChange);
    window.addEventListener("keydown", this._boundKeydown);
    window.addEventListener("mousemove", this._boundAgentGraphMouseMove);
    window.addEventListener("mouseup", this._boundAgentGraphMouseUp);
    this._boundSidebarTouchStart = this._onGlobalSidebarTouchStart.bind(this);
    this._boundSidebarTouchEnd = this._onGlobalSidebarTouchEnd.bind(this);
    window.addEventListener("touchstart", this._boundSidebarTouchStart, { passive: true });
    window.addEventListener("touchend", this._boundSidebarTouchEnd, { passive: true });
    window.addEventListener("touchcancel", this._boundSidebarTouchEnd, { passive: true });
    this._boundSwipeMove = this._onGlobalSwipeMove.bind(this);
    window.addEventListener("touchmove", this._boundSwipeMove, { passive: false });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", this._boundResize);
    }

    await this.initializeWebPushSupport();
    await this.fetchAuthStatus();
    await this.bootstrapConversations({ activateApp: false });
    // Restore in-progress regular-message sends after page reload
    try {
      const raw = sessionStorage.getItem("oathweaver_pending_jobs");
      if (raw) {
        const stored = JSON.parse(raw);
        if (stored && typeof stored === "object") {
          for (const [cid, meta] of Object.entries(stored)) {
            const rid = String(meta?.requestId || "").trim();
            if (!rid) continue;
            this.setConversationSending(cid, meta);
            this.recoverMessageRequest(cid, rid, Boolean(meta.foraging))
              .then(() => { this.setConversationSending(cid, false); })
              .catch(() => { this.setConversationSending(cid, false); });
          }
        }
      }
    } catch (_e) {}
    await this.refreshPanelBadges();
    await this.refreshProjectPipeline();
    this.loadMakeTypeCatalog().catch(() => {});
    try {
      await this.initializeHomeWeather();
    } catch (_err) {}
    if (this.auth.enabled && this.auth.authenticated) {
      this.setActiveApp("home");
    }

    this._panelPollTimer = window.setInterval(async () => {
      if (this.auth.enabled && !this.auth.authenticated) {
        return;
      }
      try {
        await this.refreshPanelBadges();
      } catch (_err) {}
      try {
        await this.refreshConversations();
      } catch (_err) {}
      if (this.webPushModalOpen) {
        try {
          await this.refreshWebPushSettings();
        } catch (_err) {}
      }
    }, 30000);

    this._homePhraseTimer = window.setInterval(() => {
      this.refreshHomePhrase();
    }, 60000);

    this._homeClockTimer = window.setInterval(() => {
      this._updateHomeClock();
    }, 30000);

    this._composerPlaceholderTimer = window.setInterval(() => {
      this.composerPlaceholderFading = true;
      setTimeout(() => {
        this.composerPlaceholderIdx += 1;
        this.composerPlaceholderFading = false;
      }, 320);
    }, 5000);

    this._homeWeatherPollTimer = window.setInterval(async () => {
      if (this.auth.enabled && !this.auth.authenticated) {
        return;
      }
      if (
        !Number.isFinite(Number(this.homeWeather.latitude)) ||
        !Number.isFinite(Number(this.homeWeather.longitude))
      ) {
        return;
      }
      try {
        await this.refreshHomeWeather({ silent: true });
      } catch (_err) {}
    }, 20 * 60 * 1000);

    this._thinkingTimer = window.setInterval(() => {
      this.thinkingNowTs = Date.now();
    }, 1000);

    await this.$nextTick();
    this._blobStopFns = [
      this._startBlobAnimation(this.$refs.chatBlobCanvas),
      this._startBlobAnimation(this.$refs.homeBlobCanvas),
    ];
  },

  beforeUnmount() {
    if (this._boundWindowClick) {
      window.removeEventListener("click", this._boundWindowClick);
    }
    if (this._boundResize) {
      window.removeEventListener("resize", this._boundResize);
      window.removeEventListener("orientationchange", this._boundResize);
      if (window.visualViewport) {
        window.visualViewport.removeEventListener("resize", this._boundResize);
      }
    }
    if (this._boundHashChange) {
      window.removeEventListener("hashchange", this._boundHashChange);
    }
    if (this._boundKeydown) {
      window.removeEventListener("keydown", this._boundKeydown);
    }
    if (this._boundAgentGraphMouseMove) {
      window.removeEventListener("mousemove", this._boundAgentGraphMouseMove);
    }
    if (this._boundAgentGraphMouseUp) {
      window.removeEventListener("mouseup", this._boundAgentGraphMouseUp);
    }
    if (this._boundSidebarTouchStart) {
      window.removeEventListener("touchstart", this._boundSidebarTouchStart);
    }
    if (this._boundSidebarTouchEnd) {
      window.removeEventListener("touchend", this._boundSidebarTouchEnd);
      window.removeEventListener("touchcancel", this._boundSidebarTouchEnd);
    }
    if (this._boundSwipeMove) {
      window.removeEventListener("touchmove", this._boundSwipeMove);
    }
    if (this._waypointPollTimer) {
      window.clearInterval(this._waypointPollTimer);
      this._waypointPollTimer = null;
    }
    if (this._panelPollTimer) {
      window.clearInterval(this._panelPollTimer);
      this._panelPollTimer = null;
    }
    if (this._homePhraseTimer) {
      window.clearInterval(this._homePhraseTimer);
      this._homePhraseTimer = null;
    }
    if (this._homeClockTimer) {
      window.clearInterval(this._homeClockTimer);
      this._homeClockTimer = null;
    }
    for (const stop of (this._blobStopFns || [])) {
      try { stop(); } catch (_) {}
    }
    this._blobStopFns = [];
    if (this._homeWeatherPollTimer) {
      window.clearInterval(this._homeWeatherPollTimer);
      this._homeWeatherPollTimer = null;
    }
    if (this._thinkingTimer) {
      window.clearInterval(this._thinkingTimer);
      this._thinkingTimer = null;
    }
    if (this._composerPlaceholderTimer) {
      window.clearInterval(this._composerPlaceholderTimer);
      this._composerPlaceholderTimer = null;
    }
    if (this._imageToolDefaultSaveTimer) {
      window.clearTimeout(this._imageToolDefaultSaveTimer);
      this._imageToolDefaultSaveTimer = null;
    }
    this.stopAllAssistantTypewriters();
  },
});

app.config.compilerOptions.delimiters = ["[[", "]]"];
app.mount("#app");
