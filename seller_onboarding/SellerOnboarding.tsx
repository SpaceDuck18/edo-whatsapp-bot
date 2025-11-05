// SellerOnboarding.tsx - React component to register seller WhatsApp mapping
import React, { useState } from "react";

export default function SellerOnboarding({ supabaseClient }) {
  const [phone, setPhone] = useState("");
  const [shopId, setShopId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const register = async () => {
    setLoading(true);
    setMessage("");
    try {
      const user = await supabaseClient.auth.getUser();
      if (!user?.data?.user) {
        setMessage("Please sign in first");
        setLoading(false);
        return;
      }
      const sellerUserId = user.data.user.id;
      const { error } = await supabaseClient
        .from("shop_whatsapp_mappings")
        .insert([{ shop_id: shopId, seller_user_id: sellerUserId, whatsapp_phone: phone }]);
      if (error) setMessage(error.message);
      else setMessage("Registered! We will verify shortly.");
    } catch (e) {
      setMessage("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 border rounded max-w-md">
      <h3 className="font-semibold mb-2">Seller WhatsApp onboarding</h3>
      <input className="w-full p-2 mb-2 border rounded" placeholder="+9198..." value={phone} onChange={(e)=>setPhone(e.target.value)} />
      <input className="w-full p-2 mb-2 border rounded" placeholder="Shop / marketplace id" value={shopId} onChange={(e)=>setShopId(e.target.value)} />
      <button className="py-2 px-4 border rounded" onClick={register} disabled={loading}>Register</button>
      {message && <div className="mt-2 text-sm">{message}</div>}
    </div>
  );
}