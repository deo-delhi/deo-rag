# Frontend Specification — Digital India Sahayak (Government Chatbot)

> A comprehensive frontend design & implementation guide for the DEO-RAG chatbot interface, inspired by modern AI assistants (ChatGPT, Copilot, Claude) with an Indian Government identity.

---

## 📸 Reference Mockups

### Generated UI Mockup

![Digital India Sahayak — Generated UI Mockup](/home/assassin/.gemini/antigravity/brain/b9f14395-7ec7-40b7-b304-6d13ce327e7f/chatbot_ui_mockup_1777995566449.png)

---

## 1. Overview

**Product Name:** Digital India Sahayak — Government Chatbot  
**Purpose:** A Retrieval-Augmented Generation (RAG) chatbot for Indian government records — enabling citizens to query government policies, schemes, acts, and services through a modern conversational interface.  
**Design Philosophy:** Modern, clean, and professional — inspired by ChatGPT, Copilot, and Claude — adapted with Indian Government branding (tri-color accents, Ashoka Chakra, Digital India identity).

---

## 2. Layout Structure

The application uses a **three-column layout** with collapsible side panels:

```
┌──────────────────────────────────────────────────────────────────────┐
│                          HEADER BAR                                  │
├────────────┬─────────────────────────────────┬───────────────────────┤
│            │                                 │                       │
│  LEFT      │     MAIN CHAT AREA              │  RIGHT                │
│  SIDEBAR   │                                 │  SIDEBAR              │
│  (Library) │                                 │  (System/LLM Role)    │
│            │                                 │                       │
│  ~220px    │        flex-grow                 │  ~260px               │
│  collapsible│                                │  collapsible           │
│            │                                 │                       │
│            ├─────────────────────────────────┤                       │
│            │        INPUT BAR                │                       │
├────────────┴─────────────────────────────────┴───────────────────────┤
│                     TRI-COLOR GRADIENT (subtle, from bottom)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Header Bar

| Element | Description |
|---|---|
| **Government Emblem / Logo** | Ashoka Chakra / National Emblem on the far left, followed by the **Digital India** logo with a small tri-color underline (saffron–white–green). |
| **Title** | `"Digital India Sahayak - Government Chatbot"` — centered, with Ashoka Chakra icon flanking both sides. |
| **Mode Selector** | Dropdown or pill: `Chat` mode (default). Future: `Search`, `Forms`. |
| **Light Mode Toggle** | Sun/Moon icon toggle — light mode is the default and primary design. |
| **Notifications** | Bell icon for alerts (e.g., new policy updates). |
| **User Avatar** | Circular avatar with initials or profile picture on the far right. |

**Styling:**
- Background: `#FFFFFF` (light) with subtle bottom border `1px solid #E5E7EB`
- Height: `56–64px`
- Sticky/fixed at the top of the viewport

---

### 3.2 Left Sidebar — Library Selection Panel

A **collapsible** left panel for document library navigation and chat management.

**Header:**
- Title: `"Library"` with a collapse toggle icon (`«`)
- Search bar: `"Search library..."` with a magnifying glass icon

**Navigation Sections:**

| Section | Icon | Description |
|---|---|---|
| **My Library** | 📁 | Saved chats & documents |
| **Government Schemes** | 🏛️ | Central & State schemes |
| **Policies & Acts** | 📜 | Acts, Rules & Notifications |
| **Services** | ⚙️ | Apply / Track / Status |
| **Departments** | 🏢 | Govt. Departments directory |
| **FAQs** | ❓ | Frequently asked questions |
| **Help & Support** | 🆘 | Get assistance |

**Footer:**
- `"+ New Chat"` button with keyboard shortcut hint (`⌘K`)

**Collapsed State:**
- Shows only icons in a narrow rail (`~48px` wide)
- Tooltip on hover for each icon
- Smooth slide animation (`300ms ease-in-out`)

**Styling:**
- Background: Dark charcoal gray `#1E1E2E` (high contrast against the light main area)
- Text: `#E5E7EB` (light gray)
- Active item: Highlighted with a subtle saffron/orange left-border accent
- Hover: `background: rgba(255,255,255,0.08)`
- Width: `220px` expanded, `48px` collapsed
- Rounded corners on the panel container: `12px`

---

### 3.3 Main Chat Area

The central and primary area of the interface.

#### 3.3.1 Welcome State (No Messages)

- Large heading: `"How can I assist you today?"`
- Subtext: `"Ask about government services, schemes, policies, or FAQs"`
- Quick-start suggestion chips below (rounded pill buttons):
  - `"Track Aadhaar Update"`
  - `"Download Forms"`
  - `"Check Scheme Eligibility"`

#### 3.3.2 Chat Messages

**User Messages (Right-aligned):**
- Background: Dark gray `#2D2D3D` or `#374151`
- Text color: White `#FFFFFF`
- Alignment: Right
- Rounded corners: `16px 16px 4px 16px` (square on bottom-right)
- Timestamp + delivery status (double-tick) below
- User initials badge on the right side

**Bot / Assistant Messages (Left-aligned):**
- Background: White `#FFFFFF`
- Text color: Dark gray `#1F2937`
- Alignment: Left
- Rounded corners: `16px 16px 16px 4px` (square on bottom-left)
- **Tri-color left border:** A `3–4px` left border with a subtle vertical gradient:
  - Top: Saffron `#FF9933`
  - Middle: White `#FFFFFF`
  - Bottom: Green `#138808`
- Bot avatar: Ashoka Chakra or Digital India icon on the left
- Action icons below each bot message: Copy 📋 | Thumbs Up 👍 | Thumbs Down 👎

**Bot Message Content Support:**
- Formatted text with bold, italics, bullet points
- Document links (clickable, styled with 🔗 icon)
- Tables for structured data
- Code blocks (if applicable)

#### 3.3.3 Quick Action Chips

Appear below the last bot message as contextual suggestions:
- Rounded pill buttons with icons
- Examples: `"Track Aadhaar Update"`, `"Download Forms"`, `"Check Scheme Eligibility"`
- Styling: Outlined, with subtle hover effect

#### 3.3.4 Input Bar

| Element | Description |
|---|---|
| **Attachment icon** | 📎 Paperclip for file uploads |
| **Text input** | Placeholder: `"Ask me anything about government services..."` |
| **Source filter pills** | Inside or below the input: `🌐 Web` · `📋 Schemes` · `📜 Policies` |
| **Voice input** | 🎤 Microphone icon |
| **Send button** | Arrow icon `➤`, highlighted in saffron/brand color when active |

**Styling:**
- Background: `#F9FAFB` with `1px solid #D1D5DB` border
- Rounded corners: `24px` (pill-shaped)
- Box shadow: `0 2px 8px rgba(0,0,0,0.06)`
- Position: Sticky at the bottom of the chat area

---

### 3.4 Right Sidebar — System / LLM Role Panel

A **collapsible** right panel displaying system metadata and current LLM configuration.

**Header:**
- Title: `"System & LLM Role"` with collapse toggle (`«`)

**Section 1: Current LLM Role**

| Field | Example Value |
|---|---|
| **Assistant Role** | `Informational / Advisory` |
| **Role Description** | `Provides accurate, up-to-date info on government policies, schemes, and processes based on official documents.` |
| **Knowledge Base** | `Govt. Library, National Portal` |
| **Response Mode** | `Verified & Factual` |
| **Data Sources** | `Official Portals` |
| **Language** | `English (EN)` |

Each field is presented as a clickable/expandable row with a `>` chevron.

**Section 2: Session Metadata**

| Field | Example Value |
|---|---|
| **Session ID** | `#GOVT-2025-08-19` |
| **Started** | `10:23 AM` |
| **Messages** | `6` |

**Footer:**
- `"View System Details"` button with external link icon `↗`

**Styling:**
- Background: Dark charcoal gray `#1E1E2E`
- Text: `#E5E7EB` (light gray), labels in `#9CA3AF`
- Section dividers: Subtle `1px solid #374151`
- Width: `260px` expanded, `0px` collapsed (slides out entirely)
- Rounded corners on the panel container: `12px`

---

## 4. Visual Design System

### 4.1 Color Palette

#### Primary Colors

| Token | Value | Usage |
|---|---|---|
| `--color-saffron` | `#FF9933` | Tri-color accent, active states, send button |
| `--color-white` | `#FFFFFF` | Tri-color accent, main background |
| `--color-green` | `#138808` | Tri-color accent, success states |
| `--color-navy` | `#000080` | Ashoka Chakra blue, link accents |

#### Neutral Colors

| Token | Value | Usage |
|---|---|---|
| `--bg-primary` | `#FAFBFC` | Main chat area background |
| `--bg-secondary` | `#F3F4F6` | Input bar, secondary areas |
| `--bg-sidebar` | `#1E1E2E` | Sidebar panels |
| `--text-primary` | `#1F2937` | Main body text |
| `--text-secondary` | `#6B7280` | Muted / secondary text |
| `--text-on-dark` | `#E5E7EB` | Text on dark backgrounds |
| `--border` | `#E5E7EB` | Borders, dividers |
| `--border-dark` | `#374151` | Borders on dark backgrounds |

#### Semantic Colors

| Token | Value | Usage |
|---|---|---|
| `--success` | `#10B981` | Success indicators |
| `--warning` | `#F59E0B` | Warning indicators |
| `--error` | `#EF4444` | Error states |
| `--info` | `#3B82F6` | Informational highlights |

### 4.2 Typography

| Element | Font | Weight | Size |
|---|---|---|---|
| **Headings** | `Inter` or `Noto Sans` | 600–700 | 20–28px |
| **Body** | `Inter` or `Noto Sans` | 400 | 14–16px |
| **Captions / Labels** | `Inter` or `Noto Sans` | 500 | 12–13px |
| **Chat messages** | `Inter` or `Noto Sans` | 400 | 15px |
| **Code** | `JetBrains Mono` | 400 | 13px |

**Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans:wght@300;400;500;600;700&display=swap');
```

### 4.3 Spacing & Layout

| Token | Value |
|---|---|
| `--spacing-xs` | `4px` |
| `--spacing-sm` | `8px` |
| `--spacing-md` | `16px` |
| `--spacing-lg` | `24px` |
| `--spacing-xl` | `32px` |
| `--radius-sm` | `8px` |
| `--radius-md` | `12px` |
| `--radius-lg` | `16px` |
| `--radius-pill` | `9999px` |

### 4.4 Shadows

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
--shadow-card: 0 2px 8px rgba(0, 0, 0, 0.06);
```

### 4.5 Tri-Color Gradient (Background)

A very subtle tri-color gradient that rises from the bottom of the main chat area:

```css
.main-chat-area {
  background: linear-gradient(
    to top,
    rgba(19, 136, 8, 0.03) 0%,       /* Green - very faint */
    rgba(255, 255, 255, 0.02) 15%,    /* White transition */
    rgba(255, 153, 51, 0.02) 30%,     /* Saffron - very faint */
    #FAFBFC 50%                        /* Solid background */
  );
}
```

### 4.6 Tri-Color Border on Bot Messages

```css
.bot-message {
  border-left: 4px solid;
  border-image: linear-gradient(
    to bottom,
    #FF9933 0%,     /* Saffron */
    #FFFFFF 50%,    /* White */
    #138808 100%    /* Green */
  ) 1;
}
```

---

## 5. Animations & Interactions

### 5.1 Sidebar Collapse/Expand

```css
.sidebar {
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.sidebar.collapsed {
  width: 48px; /* Left sidebar icon rail */
}
.sidebar.right.collapsed {
  width: 0px; /* Right sidebar hides completely */
}
```

### 5.2 Chat Message Entry

- Messages fade in + slide up: `opacity 0→1, translateY(8px→0)` over `300ms`
- Bot typing indicator: Three pulsing dots animation

### 5.3 Hover Effects

- Sidebar items: Background opacity shift on hover
- Chat action icons: Scale up `1→1.1` + color change on hover
- Buttons: Subtle elevation change (`shadow-sm → shadow-md`)

### 5.4 Input Focus

- Border color transitions to saffron `#FF9933` on focus
- Subtle glow: `box-shadow: 0 0 0 3px rgba(255, 153, 51, 0.15)`

### 5.5 Scroll Behavior

- Smooth scroll to bottom on new message
- "Scroll to bottom" floating button when user scrolls up
- Custom scrollbar styling (thin, dark on light backgrounds)

---

## 6. Responsive Behavior

| Breakpoint | Layout Changes |
|---|---|
| **≥ 1280px** | Full three-column layout |
| **1024–1279px** | Left sidebar collapsed by default, right sidebar hidden |
| **768–1023px** | Both sidebars hidden, accessible via hamburger menu / swipe |
| **< 768px** | Single-column mobile layout, bottom sheet for panels |

### Mobile Specifics

- Header compacts: Logo + hamburger only
- Input bar sticks to bottom
- Sidebars open as overlay drawers
- Chat bubbles span full width with reduced padding

---

## 7. Component Hierarchy (React)

```
<App>
├── <Header />
│   ├── <Logo />
│   ├── <Title />
│   ├── <ModeSelector />
│   ├── <ThemeToggle />
│   ├── <NotificationBell />
│   └── <UserAvatar />
│
├── <MainLayout>
│   ├── <LeftSidebar collapsed={bool}>
│   │   ├── <SidebarHeader />
│   │   ├── <SearchBar />
│   │   ├── <NavSection title="Library">
│   │   │   ├── <NavItem icon label />
│   │   │   └── ...
│   │   ├── <NavSection title="Services">
│   │   │   └── ...
│   │   └── <NewChatButton />
│   │
│   ├── <ChatArea>
│   │   ├── <WelcomeScreen /> (when no messages)
│   │   ├── <MessageList>
│   │   │   ├── <UserMessage />
│   │   │   ├── <BotMessage>
│   │   │   │   ├── <MessageContent /> (markdown rendering)
│   │   │   │   ├── <DocumentLinks />
│   │   │   │   └── <MessageActions /> (copy, thumbs up/down)
│   │   │   └── ...
│   │   ├── <QuickActionChips />
│   │   └── <TypingIndicator />
│   │
│   ├── <InputBar>
│   │   ├── <AttachButton />
│   │   ├── <TextInput />
│   │   ├── <SourceFilters /> (Web, Schemes, Policies)
│   │   ├── <VoiceButton />
│   │   └── <SendButton />
│   │
│   └── <RightSidebar collapsed={bool}>
│       ├── <SidebarHeader />
│       ├── <LLMRoleSection>
│       │   ├── <RoleField label value />
│       │   └── ...
│       ├── <SessionMetadata>
│       │   ├── <MetaField label value />
│       │   └── ...
│       └── <SystemDetailsButton />
│
└── <TriColorGradientOverlay /> (CSS-only, decorative)
```

---

## 8. State Management

| State | Description | Scope |
|---|---|---|
| `messages[]` | Chat message history | Global (Context/Zustand) |
| `isLeftSidebarOpen` | Left panel visibility | Global |
| `isRightSidebarOpen` | Right panel visibility | Global |
| `currentLibrary` | Selected library/data source | Global |
| `llmRole` | Current system role configuration | Global |
| `sessionMetadata` | Session ID, start time, message count | Global |
| `isTyping` | Whether bot is generating a response | Global |
| `inputValue` | Current input field value | Local (InputBar) |
| `activeSourceFilters` | Active source filter pills | Local (InputBar) |
| `theme` | `'light'` or `'dark'` | Global |

---

## 9. API Integration Points

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | `POST` | Send user message, receive streamed bot response |
| `/api/libraries` | `GET` | Fetch available libraries/data sources |
| `/api/documents` | `GET` | List documents in selected library |
| `/api/session` | `GET/POST` | Manage chat sessions |
| `/api/system-role` | `GET` | Fetch current LLM role configuration |
| `/api/feedback` | `POST` | Submit thumbs up/down feedback |

---

## 10. Accessibility

- Full keyboard navigation support
- ARIA labels on all interactive elements
- Focus trapping in modals/drawers
- Screen reader-friendly message announcements
- Minimum contrast ratio: `4.5:1` (WCAG AA)
- Support for reduced motion preferences

---

## 11. Key Design Principles

1. **Government Identity, Modern Execution** — Indian tri-color and national symbols integrated tastefully, not overwhelmingly.
2. **High Contrast** — Dark sidebars against light center creates visual hierarchy and focus on the conversation.
3. **Progressive Disclosure** — Collapsible panels keep the interface clean while making power-user features accessible.
4. **Familiar Patterns** — Users of ChatGPT, Copilot, or Claude will immediately feel at home.
5. **Content-First** — The chat area dominates the layout, keeping the focus on the conversation.
6. **Responsive & Inclusive** — Works across devices and meets accessibility standards.

---

## 12. Tech Stack (Frontend)

| Technology | Purpose |
|---|---|
| **React 18** | UI framework |
| **Vite** | Build tool & dev server |
| **Vanilla CSS** (CSS Modules or scoped) | Styling — no Tailwind |
| **Google Fonts (Inter / Noto Sans)** | Typography |
| **React Markdown** | Rendering bot message content |
| **Zustand** or **React Context** | State management |
| **Framer Motion** (optional) | Animations & transitions |

---

> **Note:** This document serves as the single source of truth for the frontend design and implementation. All UI development should reference this specification for layout, styling, and component structure.
