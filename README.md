# robopay

**Open payment rails for autonomous robots.** An open-source ROS 2 library that
lets robots send and receive **USDC** payments triggered by real-world
conditions - settled peer-to-peer on Base.

> Open-source. Free. MIT-Licensed.

Part of the [Open Robot Economy](https://openroboteconomy.org).

---

## What it does

Bind a payment to a physical condition, in your robot's own code:

```python
from robopay import RobotWallet

wallet = RobotWallet.local(chain="base", asset="USDC")   # self-custody by default
wallet.pay(to="did:pkh:...charger", amount="0.05")       # a robot pays for power
```

## Status

Pre-alpha. This repository is the **Phase 0 skeleton**: the four packages, the
service/action interfaces, a deterministic mock backend, a runnable payment
node, and the CLI entry point. See the build plan for what lands next.

## Packages

| Package | What it is |
| --- | --- |
| `robopay_interfaces` | `.srv` / `.action` type definitions |
| `robopay_core` | the `payment_node`, wallet providers, settlement backends, CLI |
| `robopay_conditions` | the `condition_node` - binds predicates to payments |
| `robopay_examples` | configs and the turtlesim demo |

## Backends

| Backend | Role | Status |
| --- | --- | --- |
| `mock` | first-run demo & tests - no chain, no money | working |
| `self_custody` | **the default real backend** - robot holds its own key (web3.py) | Phase 2 |
| `circle` | opt-in managed MPC + gas abstraction, for fleets | Phase 8 |

## Quickstart (dev container)

Requires Docker Desktop + VS Code + the **Dev Containers** extension.

```bash
git clone https://github.com/<you>/robopay.git
code robopay          # then: "Reopen in Container"
```

Inside the container:

```bash
colcon build
source install/setup.bash

# run the payment node (mock backend - no chain, no money)
ros2 run robopay_core payment_node
```

In a second terminal (remember to `source install/setup.bash`):

```bash
ros2 service call /wallet/create robopay_interfaces/srv/WalletCreate "{label: 'robot-a'}"

ros2 service call /transfer/send robopay_interfaces/srv/Transfer \
  "{from_address: '0x...', to_address: '0xbob', amount: '2.50', asset: 'USDC'}"
```

Run the pure-Python tests (no ROS needed):

```bash
pytest src/robopay_core/test
```

## Supported ROS 2 distros
Humble (Ubuntu 22.04). CI also builds Jazzy and Lyrical.

## License

MIT.
