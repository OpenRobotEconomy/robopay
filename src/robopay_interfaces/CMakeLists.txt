cmake_minimum_required(VERSION 3.8)
project(robopay_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/Transfer.srv"
  "srv/TransferPreview.srv"
  "srv/WalletCreate.srv"
  "srv/WalletBalance.srv"
  "srv/PaymentRequest.srv"
  "srv/IdentityRegister.srv"
  "srv/IdentityResolve.srv"
  "srv/ProofSign.srv"
  "srv/EscrowSign.srv"
  "srv/EscrowSubmitSignature.srv"
  "action/Escrow.action"
  "msg/EscrowSignature.msg"
  DEPENDENCIES action_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
