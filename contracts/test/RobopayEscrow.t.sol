// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {RobopayEscrow} from "../src/RobopayEscrow.sol";

contract MockToken {
    string public name = "Mock USD";
    uint8 public decimals = 6;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amt) external { balanceOf[to] += amt; }
    function approve(address s, uint256 a) external returns (bool) {
        allowance[msg.sender][s] = a; return true;
    }
    function transferFrom(address f, address t, uint256 a) external returns (bool) {
        require(allowance[f][msg.sender] >= a, "not approved");
        allowance[f][msg.sender] -= a;
        require(balanceOf[f] >= a, "insufficient");
        balanceOf[f] -= a; balanceOf[t] += a; return true;
    }
    function transfer(address t, uint256 a) external returns (bool) {
        require(balanceOf[msg.sender] >= a, "insufficient");
        balanceOf[msg.sender] -= a; balanceOf[t] += a; return true;
    }
}

contract RobopayEscrowTest is Test {
    RobopayEscrow escrow;
    MockToken token;

    uint256 payerPk = 0xA11CE;
    uint256 payeePk = 0xB0B;
    address payer;
    address payee;
    uint256 nonceCounter;

    function setUp() public {
        token = new MockToken();
        address[] memory allowed = new address[](1);
        allowed[0] = address(token);
        escrow = new RobopayEscrow(allowed);
        payer = vm.addr(payerPk);
        payee = vm.addr(payeePk);
        token.mint(payer, 100e6);
    }

    function _open() internal returns (bytes32 id) {
        vm.startPrank(payer);
        token.approve(address(escrow), 10e6);
        id = escrow.open(payee, address(token), 10e6,
                         block.timestamp + 1 hours, keccak256("terms"), nonceCounter++);
        vm.stopPrank();
    }

    function _sign(uint256 pk, bytes32 id) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, escrow.releaseDigest(id));
        return abi.encodePacked(r, s, v);
    }

    // ---------- functional ----------

    function test_open_locks_funds() public {
        _open();
        assertEq(token.balanceOf(address(escrow)), 10e6);
        assertEq(token.balanceOf(payer), 90e6);
    }

    function test_release_pays_payee_with_valid_sigs() public {
        bytes32 id = _open();
        escrow.release(id, _sign(payerPk, id), _sign(payeePk, id));
        assertEq(token.balanceOf(payee), 10e6);
        assertEq(token.balanceOf(address(escrow)), 0);
    }

    function test_refund_returns_funds_after_deadline() public {
        bytes32 id = _open();
        vm.warp(block.timestamp + 2 hours);
        escrow.refund(id);
        assertEq(token.balanceOf(payer), 100e6);
        assertEq(token.balanceOf(address(escrow)), 0);
    }

    function test_cannot_refund_before_deadline() public {
        bytes32 id = _open();
        vm.expectRevert("deadline not reached");
        escrow.refund(id);
    }

    // ---------- state machine exclusivity ----------

    function test_cannot_release_twice() public {
        bytes32 id = _open();
        bytes memory p = _sign(payerPk, id);
        bytes memory e = _sign(payeePk, id);
        escrow.release(id, p, e);
        vm.expectRevert("escrow not locked");
        escrow.release(id, p, e);
    }

    function test_cannot_refund_a_released_escrow() public {
        bytes32 id = _open();
        escrow.release(id, _sign(payerPk, id), _sign(payeePk, id));
        vm.warp(block.timestamp + 2 hours);
        vm.expectRevert("escrow not locked");
        escrow.refund(id);
    }

    function test_cannot_release_a_refunded_escrow() public {
        bytes32 id = _open();
        vm.warp(block.timestamp + 2 hours);
        escrow.refund(id);
        bytes memory p = _sign(payerPk, id);
        bytes memory e = _sign(payeePk, id);
        vm.expectRevert("escrow not locked");
        escrow.release(id, p, e);
    }

    // ---------- security / attacks ----------

    function test_release_rejects_wrong_signer() public {
        bytes32 id = _open();
        bytes memory wrongPayer = _sign(payeePk, id);   // payee key in payer slot
        bytes memory e = _sign(payeePk, id);
        vm.expectRevert("invalid payer signature");
        escrow.release(id, wrongPayer, e);
    }

    function test_signatures_cannot_be_replayed_across_escrows() public {
        bytes32 idA = _open();
        bytes32 idB = _open();
        bytes memory pA = _sign(payerPk, idA);
        bytes memory eA = _sign(payeePk, idA);
        vm.expectRevert("invalid payer signature");
        escrow.release(idB, pA, eA);
    }

    function test_garbage_signature_is_rejected() public {
        bytes32 id = _open();
        bytes memory garbage = new bytes(65);
        bytes memory e = _sign(payeePk, id);
        vm.expectRevert("invalid payer signature");
        escrow.release(id, garbage, e);
    }

    function test_cannot_release_nonexistent_escrow() public {
        bytes32 ghost = keccak256("ghost");
        bytes memory p = _sign(payerPk, ghost);
        bytes memory e = _sign(payeePk, ghost);
        vm.expectRevert("escrow not locked");
        escrow.release(ghost, p, e);
    }

    function test_cannot_open_with_zero_payee() public {
        vm.startPrank(payer);
        token.approve(address(escrow), 10e6);
        vm.expectRevert("payee cannot be zero");
        escrow.open(address(0), address(token), 10e6,
                    block.timestamp + 1 hours, keccak256("terms"), 99);
        vm.stopPrank();
    }

    function test_cannot_open_with_escrow_as_payee() public {
        vm.startPrank(payer);
        token.approve(address(escrow), 10e6);
        vm.expectRevert("payee cannot be this contract");
        escrow.open(address(escrow), address(token), 10e6,
                    block.timestamp + 1 hours, keccak256("terms"), 98);
        vm.stopPrank();
    }

    function test_disallowed_token_is_rejected() public {
        MockToken other = new MockToken();
        other.mint(payer, 50e6);
        vm.startPrank(payer);
        other.approve(address(escrow), 10e6);
        vm.expectRevert("token not allowed");
        escrow.open(payee, address(other), 10e6,
                    block.timestamp + 1 hours, keccak256("terms"), 97);
        vm.stopPrank();
    }

    // ATTACK: an attacker cannot squat an id belonging to a different payer,
    // because the derived id includes msg.sender.
    function test_attacker_cannot_squat_payer_id() public {
        address attacker = address(0xBAD);
        token.mint(attacker, 50e6);

        // attacker opens with the SAME parameters the payer would use
        vm.startPrank(attacker);
        token.approve(address(escrow), 10e6);
        bytes32 attackerId = escrow.open(payee, address(token), 10e6,
                                         block.timestamp + 1 hours, keccak256("terms"), 0);
        vm.stopPrank();

        // the payer can still open with identical params — different id
        vm.startPrank(payer);
        token.approve(address(escrow), 10e6);
        bytes32 payerId = escrow.open(payee, address(token), 10e6,
                                      block.timestamp + 1 hours, keccak256("terms"), 0);
        vm.stopPrank();

        assertTrue(attackerId != payerId, "ids must differ by msg.sender");
    }

    function test_same_params_same_nonce_cannot_be_reopened() public {
        vm.startPrank(payer);
        token.approve(address(escrow), 20e6);
        escrow.open(payee, address(token), 10e6,
                    block.timestamp + 1 hours, keccak256("terms"), 42);
        vm.expectRevert("escrow id already used");
        escrow.open(payee, address(token), 10e6,
                    block.timestamp + 1 hours, keccak256("terms"), 42);
        vm.stopPrank();
    }
}