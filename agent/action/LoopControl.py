'''
在流水线/节点执行过程中基于计数动态中断循环跳转，从而控制流程退出循环。
'''


from maa.custom_action import CustomAction  
from maa.context import Context  
  
class LoopControlAction(CustomAction):  
    """  
    Custom action that monitors node B's hit count and modifies   
    node A's next list to exit the loop when a threshold is reached.  
    """  
      
    def run(  
        self,  
        context: Context,  
        argv: CustomAction.RunArg,  
    ) -> CustomAction.RunResult:  
        '''
        自定义动作：
        custom_action_param:
            {
                "count": 0,
                "target_count": 10,
                "next_node": ["node1", "node2"],
                "else_node": ["node3"],
            }
        LoopCount 控制逻辑：
        1. 获取节点 B 的命中计数。
        2. 定义一个阈值，当命中计数达到该阈值时，执行跳出循环的操作。
        3. 如果命中计数达到阈值，修改节点 A 的 next 列表，移除跳转回节点 A 的跳转节点，从而打破循环。
        4. 返回成功状态，表示操作已完成。
        5. 如果未达到阈值，继续循环，返回成功状态。
        参数:
            context (Context): 当前执行上下文，包含节点信息和状态。
            argv (CustomAction.RunArg): 运行参数，包含自定义动作的输入参数。
        '''
        # 1. Get the hit count of node B  
        node_b_hit_count = context.get_hit_count("NodeB")  
        print(f"NodeB has been hit {node_b_hit_count} times")  
          
        # 2. Define threshold for exiting the loop  
        MAX_LOOP_COUNT = 5  
          
        # 3. Check if we should exit the loop  
        if node_b_hit_count >= MAX_LOOP_COUNT:  
            print(f"Reached max count ({MAX_LOOP_COUNT}), exiting loop")  
              
            # 4. Modify NodeA's next list to remove the JumpBack node  
            # This breaks the loop by preventing jumping back to NodeA  
            success = context.override_next("NodeA", ["NodeC"])  # Skip to exit node  
              
            if success:  
                print("Successfully modified NodeA's next list to exit loop")  
            else:  
                print("Failed to modify NodeA's next list")  
                  
            return CustomAction.RunResult(success=success)  
          
        # 5. Loop should continue - return success  
        return CustomAction.RunResult(success=True)