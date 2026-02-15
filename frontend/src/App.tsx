import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import TopBar from "@/ui/TopBar";
import NavBar from "@/ui/NavBar";
import Auth from "@/screens/Auth";
import Home from "@/screens/Home";
import Deals from "@/screens/Deals";
import Profile from "@/screens/Profile";
import Search from "@/screens/Search";
import Channels from "@/screens/Channels";
import AddChannel from "@/screens/AddChannel";
import ChannelDetail from "@/screens/ChannelDetail";
import Campaigns from "@/screens/Campaigns";
import CampaignForm from "@/screens/CampaignForm";
import DealDetail from "@/screens/DealDetail";
import SearchDetail from "@/screens/SearchDetail";
import Listings from "@/screens/Listings";
import ListingForm from "@/screens/ListingForm";
import CampaignSearch from "@/screens/CampaignSearch";
import CampaignSearchDetail from "@/screens/CampaignSearchDetail";
import ChannelPublicView from "@/screens/ChannelPublicView";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth();

  if (loading) return null;
  if (!authenticated) return <Navigate to="/" replace />;

  return <>{children}</>;
}

function App() {
  const t = useTheme();
  const { user } = useAuth();
  const { i18n } = useTranslation();

  useEffect(() => {
    if (user && user.locale !== i18n.language) {
      i18n.changeLanguage(user.locale);
    }
  }, [user, i18n]);

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: t.bg,
        color: t.text,
        overflow: "hidden",
      }}
    >
      <TopBar />
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          padding: "0 16px",
          WebkitOverflowScrolling: "touch",
        }}
      >
        <Routes>
          <Route path="/" element={<Auth />} />
          <Route path="/home" element={<ProtectedRoute><Home /></ProtectedRoute>} />
          <Route path="/deals" element={<ProtectedRoute><Deals /></ProtectedRoute>} />
          <Route path="/deals/:id" element={<ProtectedRoute><DealDetail /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/search" element={<ProtectedRoute><Search /></ProtectedRoute>} />
          <Route path="/channels" element={<ProtectedRoute><Channels /></ProtectedRoute>} />
          <Route path="/channels/add" element={<ProtectedRoute><AddChannel /></ProtectedRoute>} />
          <Route path="/channels/:id" element={<ProtectedRoute><ChannelDetail /></ProtectedRoute>} />
          <Route path="/campaigns" element={<ProtectedRoute><Campaigns /></ProtectedRoute>} />
          <Route path="/campaigns/new" element={<ProtectedRoute><CampaignForm /></ProtectedRoute>} />
          <Route path="/campaigns/:id/edit" element={<ProtectedRoute><CampaignForm /></ProtectedRoute>} />
          <Route path="/campaigns/:id" element={<ProtectedRoute><CampaignForm /></ProtectedRoute>} />
          <Route path="/search/:id" element={<ProtectedRoute><SearchDetail /></ProtectedRoute>} />
          <Route path="/listings" element={<ProtectedRoute><Listings /></ProtectedRoute>} />
          <Route path="/listings/new" element={<ProtectedRoute><ListingForm /></ProtectedRoute>} />
          <Route path="/listings/:id/edit" element={<ProtectedRoute><ListingForm /></ProtectedRoute>} />
          <Route path="/campaign-search" element={<ProtectedRoute><CampaignSearch /></ProtectedRoute>} />
          <Route path="/campaign-search/:id" element={<ProtectedRoute><CampaignSearchDetail /></ProtectedRoute>} />
          <Route path="/channel-view/:id" element={<ProtectedRoute><ChannelPublicView /></ProtectedRoute>} />
        </Routes>
      </main>
      <NavBar />
    </div>
  );
}

export default App;
