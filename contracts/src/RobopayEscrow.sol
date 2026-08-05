// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {SignatureChecker} from "@openzeppelin/contracts/utils/cryptography/SignatureChecker.sol";


contract RobopayEscrow is EIP712 {
    using SafeERC20 for IERC20;

    enum State { None, Locked, Released, Refunded }

    
    struct Escrow {
        address payer;
        State   state;
        address payee;
        address token;
        uint256 amount;
        uint256 deadline;
        bytes32 terms;
    }

   
    bytes32 private constant RELEASE_TYPEHASH = keccak256(
        "Release(bytes32 id,address payee,address token,uint256 amount,uint256 deadline,bytes32 terms)"
    );

    mapping(bytes32 => Escrow) public escrows;

    
    mapping(address => bool) public allowedTokens;
    address public immutable admin;

    event Opened(bytes32 indexed id, address indexed payer, address indexed payee,
                 address token, uint256 amount, uint256 deadline, bytes32 terms);
    event Released(bytes32 indexed id, address indexed payee, uint256 amount);
    event Refunded(bytes32 indexed id, address indexed payer, uint256 amount);

    constructor(address[] memory initialTokens) EIP712("RobopayEscrow", "1") {
        admin = msg.sender;
        for (uint256 i = 0; i < initialTokens.length; i++) {
            allowedTokens[initialTokens[i]] = true;
        }
    }

    function setTokenAllowed(address token, bool allowed) external {
        require(msg.sender == admin, "not admin");
        allowedTokens[token] = allowed;
    }

    
    function open(
        address payee,
        address token,
        uint256 amount,
        uint256 deadline,
        bytes32 terms,
        uint256 nonce
    ) external returns (bytes32 id) {
        require(allowedTokens[token], "token not allowed");
        require(payee != address(0), "payee cannot be zero");
        require(payee != address(this), "payee cannot be this contract");
        require(amount > 0, "amount must be positive");
        require(deadline > block.timestamp, "deadline must be in the future");

        id = keccak256(abi.encode(
            block.chainid, address(this), msg.sender, payee, token, amount, deadline, terms, nonce
        ));
        require(escrows[id].state == State.None, "escrow id already used");

        
        escrows[id] = Escrow({
            payer: msg.sender,
            state: State.Locked,
            payee: payee,
            token: token,
            amount: amount,
            deadline: deadline,
            terms: terms
        });

        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        emit Opened(id, msg.sender, payee, token, amount, deadline, terms);
    }

    
    function releaseDigest(bytes32 id) public view returns (bytes32) {
        Escrow storage e = escrows[id];
        return _hashTypedDataV4(keccak256(abi.encode(
            RELEASE_TYPEHASH, id, e.payee, e.token, e.amount, e.deadline, e.terms
        )));
    }

    
    function release(bytes32 id, bytes calldata payerSig, bytes calldata payeeSig) external {
        Escrow storage e = escrows[id];
        require(e.state == State.Locked, "escrow not locked");

        bytes32 digest = releaseDigest(id);
        require(SignatureChecker.isValidSignatureNow(e.payer, digest, payerSig),
                "invalid payer signature");
        require(SignatureChecker.isValidSignatureNow(e.payee, digest, payeeSig),
                "invalid payee signature");

        e.state = State.Released;
        IERC20(e.token).safeTransfer(e.payee, e.amount);

        emit Released(id, e.payee, e.amount);
    }

    
    function refund(bytes32 id) external {
        Escrow storage e = escrows[id];
        require(e.state == State.Locked, "escrow not locked");
        require(block.timestamp > e.deadline, "deadline not reached");

        e.state = State.Refunded;
        IERC20(e.token).safeTransfer(e.payer, e.amount);

        emit Refunded(id, e.payer, e.amount);
    }
}