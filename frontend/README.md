# MDBQS Frontend

A React + Vite application for the MDBQS (Multi-Database Query System) project.

## Project Structure

```
src/
├── api/           # API utilities and services
├── components/    # Reusable React components
├── store/         # Zustand stores for state management
├── hooks/         # Custom React hooks
├── types/         # TypeScript type definitions
├── App.tsx        # Main App component
├── main.tsx       # Application entry point
└── index.css      # Global styles
```

## Getting Started

### Prerequisites
- Node.js >= 16
- npm or yarn

### Installation

```bash
npm install
```

### Development Server

```bash
npm run dev
```

The application will open at `http://localhost:5173`

### Building

```bash
npm run build
```

### Preview

```bash
npm run preview
```

## Technologies

- **React 18.2** - UI framework
- **Vite 5.0** - Build tool
- **TypeScript** - Type safety
- **Zustand** - State management

## Components

### Layout Components
- `ChatLayout` - Main layout wrapper
- `TopNavbar` - Navigation bar
- `Sidebar` - Sidebar panel

### Chat Components
- `ChatWindow` - Chat message display area
- `UserMessageBubble` - User message display
- `AssistantMessageBubble` - Assistant message display
- `QueryInput` - Input field for queries
- `AssistantResponse` - Formatted assistant response

### Data Display Components
- `CustomersTable` - Display customers in table format
- `OrdersTable` - Display orders in table format
- `ReferralsTable` - Display referrals in table format
- `OrdersChart` - Chart visualization for orders
- `CustomerCard` - Card component for single customer
- `SimilarCustomersList` - List of similar customers
- `SimilarCustomerCard` - Individual similar customer card

### Utility Components
- `SuggestionDropdown` - Dropdown with suggestions
- `LoadingIndicator` - Loading spinner
- `RelationshipBadge` - Badge for relationships
- `GraphPlaceholder` - Placeholder for graph views
- `ExplainChips` - Chips for explanations
- `ProvenanceDrawer` - Drawer for provenance information

## Store Management

The application uses Zustand for state management:

- **chatStore** - Manages chat messages
- **historyStore** - Manages query history
- **uiStore** - Manages UI state (theme, sidebar, loading)

## Hooks

- **useQuery** - Custom hook for querying API
- **useTheme** - Custom hook for theme management

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## License

MIT
