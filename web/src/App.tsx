import { Navigate, Outlet, Route, Routes, useParams } from "react-router";

import { Layout } from "./components/Layout";
import { demoStore } from "./lib/stores";
import { SessionProvider } from "./lib/session";
import { CheckoutPage } from "./pages/CheckoutPage";
import { HomePage } from "./pages/HomePage";
import { OrderPage } from "./pages/OrderPage";
import { StorePage } from "./pages/StorePage";

function StoreScope() {
  const { store = "" } = useParams();
  if (!demoStore(store)) return <Navigate to="/" replace />;
  return (
    <SessionProvider key={store} store={store}>
      <Layout>
        <Outlet />
      </Layout>
    </SessionProvider>
  );
}

export default function App() {
  return (
    <Routes>
      <Route index element={<HomePage />} />
      <Route path=":store" element={<StoreScope />}>
        <Route index element={<StorePage />} />
        <Route path="checkout" element={<CheckoutPage />} />
        <Route path="orders/:orderId" element={<OrderPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
