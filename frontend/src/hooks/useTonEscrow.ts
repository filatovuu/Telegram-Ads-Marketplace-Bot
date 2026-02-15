import { useCallback, useEffect, useRef, useState } from "react";
import { useTonConnectUI, useTonAddress } from "@tonconnect/ui-react";
import { updateWallet, disconnectWallet } from "@/api/escrow";

// Tact-generated opcode for `message Deposit {}` — stored as base64 BOC
// Cell contains: store_uint(1243991607, 32)  i.e. opcode 0x4A25CE37
const DEPOSIT_PAYLOAD_BOC = "te6ccgEBAQEABgAACEolzjc=";

export function useTonEscrow() {
  const [tonConnectUI] = useTonConnectUI();
  const walletAddress = useTonAddress();
  const connected = !!walletAddress;
  const [sending, setSending] = useState(false);

  // Sync wallet address to backend on connect AND disconnect
  const wasConnectedRef = useRef(false);
  useEffect(() => {
    if (walletAddress) {
      updateWallet(walletAddress).catch(() => {
        /* best effort */
      });
      wasConnectedRef.current = true;
    } else if (wasConnectedRef.current) {
      wasConnectedRef.current = false;
      updateWallet(null).catch(() => {
        /* best effort — clear backend wallet on TonConnect disconnect */
      });
    }
  }, [walletAddress]);

  const connect = useCallback(() => {
    tonConnectUI.openModal();
  }, [tonConnectUI]);

  const disconnect = useCallback(async () => {
    const result = await disconnectWallet(false);
    if (!result.disconnected && result.active_deal_count > 0) {
      const confirmed = window.confirm(
        result.warning || "You have active deals. Disconnect wallet anyway?",
      );
      if (!confirmed) return;
      await disconnectWallet(true);
    }
    await tonConnectUI.disconnect();
  }, [tonConnectUI]);

  const sendDeposit = useCallback(
    async (toAddress: string, amountTon: number, stateInit?: string) => {
      if (!connected) {
        throw new Error("Wallet not connected");
      }
      setSending(true);
      try {
        const amountNano = Math.floor(amountTon * 1_000_000_000).toString();
        const msg: { address: string; amount: string; stateInit?: string; payload?: string } = {
          address: toAddress,
          amount: amountNano,
          payload: DEPOSIT_PAYLOAD_BOC,
        };
        if (stateInit) {
          msg.stateInit = stateInit;
        }
        console.log("[TonEscrow] sendTransaction msg:", JSON.stringify(msg).slice(0, 300));
        await tonConnectUI.sendTransaction({
          validUntil: Math.floor(Date.now() / 1000) + 600, // 10 min
          messages: [msg],
        });
      } finally {
        setSending(false);
      }
    },
    [connected, tonConnectUI],
  );

  return {
    walletAddress,
    connected,
    connect,
    disconnect,
    sendDeposit,
    sending,
  };
}
