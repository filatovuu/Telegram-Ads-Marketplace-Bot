import "@stdlib/deploy";

message Deposit {}
message Release {}
message Refund {}

contract Escrow with Deployable {
    dealId: Int as uint64;
    advertiser: Address;
    owner: Address;
    platform: Address;
    amount: Int as coins;
    feePercent: Int as uint8; // 0..100, platform fee percentage
    state: Int as uint8; // 0=init, 1=funded, 2=released, 3=refunded

    init(
        dealId: Int,
        advertiser: Address,
        owner: Address,
        platform: Address,
        amount: Int,
        feePercent: Int,
    ) {
        self.dealId = dealId;
        self.advertiser = advertiser;
        self.owner = owner;
        self.platform = platform;
        self.amount = amount;
        self.feePercent = feePercent;
        self.state = 0;
    }

    // Advertiser deposits TON into the escrow
    receive(msg: Deposit) {
        require(self.state == 0, "Escrow: not in init state");
        require(sender() == self.advertiser, "Escrow: only advertiser can deposit");
        require(context().value >= self.amount, "Escrow: insufficient deposit");
        self.state = 1;
    }

    // Platform releases funds: owner gets (amount - fee), platform gets remainder
    receive(msg: Release) {
        require(self.state == 1, "Escrow: not funded");
        require(sender() == self.platform, "Escrow: only platform can release");
        self.state = 2;
        let fee: Int = self.amount * self.feePercent / 100;
        let ownerAmount: Int = self.amount - fee;
        send(SendParameters{
            to: self.owner,
            value: ownerAmount,
            mode: SendPayGasSeparately,
            bounce: false,
            body: "Escrow released".asComment(),
        });
        // Platform gets fee + trigger value back; destroy contract
        send(SendParameters{
            to: self.platform,
            value: 0,
            mode: SendRemainingBalance | SendDestroyIfZero,
            bounce: false,
            body: "Platform fee".asComment(),
        });
    }

    // Platform refunds funds to the advertiser.
    // Deposit goes to advertiser, trigger gas returns to platform.
    receive(msg: Refund) {
        require(self.state == 1, "Escrow: not funded");
        require(sender() == self.platform, "Escrow: only platform can refund");
        self.state = 3;
        // Send the deposit (minus gas) to advertiser
        send(SendParameters{
            to: self.advertiser,
            value: self.amount,
            mode: SendPayGasSeparately,
            bounce: false,
            body: "Escrow refunded".asComment(),
        });
        // Return trigger value to platform; destroy contract
        send(SendParameters{
            to: self.platform,
            value: 0,
            mode: SendRemainingBalance | SendDestroyIfZero,
            bounce: false,
            body: "Refund gas return".asComment(),
        });
    }

    // Getters

    get fun escrowState(): Int {
        return self.state;
    }

    get fun escrowData(): EscrowData {
        return EscrowData{
            dealId: self.dealId,
            advertiser: self.advertiser,
            owner: self.owner,
            platform: self.platform,
            amount: self.amount,
            feePercent: self.feePercent,
            state: self.state,
        };
    }
}

struct EscrowData {
    dealId: Int as uint64;
    advertiser: Address;
    owner: Address;
    platform: Address;
    amount: Int as coins;
    feePercent: Int as uint8;
    state: Int as uint8;
}
