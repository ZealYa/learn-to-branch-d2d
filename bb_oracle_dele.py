# -*- coding:utf-8 -*-
#--------------------------------------------------------
# for training process
# b&b algorithm with oracle prune plicy
#--------------------------------------------------------

import math
import sys
import numpy as np
import matlab
import matlab.engine
import os
from sklearn import preprocessing
import re


eng = matlab.engine.start_matlab()

class TreeNode:
    def __init__(self,rho_d,depth):
        self.rho_d = rho_d     # the value of determined rho 
        self.depth = depth # node depth (0 for root node) 
        self.p = np.array([]) #relaxed power
        self.rho_opt = np.array([])     # relaxed optimal rho
        self.upper = sys.maxsize    # local upper bound
        self.exitflag = sys.maxsize     # flag for feasible solutions existing or not
        self.fathomed_flag = 0 # whether pruned (1) or not (0) by original prune policy
        self.global_lower_bound = sys.maxsize # gloabl lower bound
        self.status = 0 
        self.parent = None # parent nodes
        self.plunge_depth = -1
        self.estobj = sys.maxsize
        self.gapobj = sys.maxsize
        self.leaf = -1 # whether leaf node
        self.solfound = 0
        self.branch = 0
        self.power = 0 # power feature: p_kl_max/p_max_d
        self.channel = 0 # CSI feature: log(1+1/(a_kl+b_kl))/R_min_c

    def setPlungeDepth(self,pdepth):
        # Set PlungeDepth according to number of while-loop iterations
        self.plunge_depth += pdepth
        pass


# using matlab to solve the relaxed problem
# input: node
# output: rho,yita_max,exitflag
def minlp_solve(node):
    print("minlp_solving...")
    rho_d = matlab.double(node.rho_d.tolist())
    rho,p,yita_max,exitflag = eng.minlp_solve(K,L,R_min_C,P_max_D,P_max_C,h_CD,h_D,h_CB,h_DB, rho_d,nargout=4)
    if exitflag >= 0:
        rho = np.array(rho).squeeze(1)
        p = np.array(p).squeeze(1)
    return rho,p,yita_max,exitflag

# using matlab to compute paramters
# output: a,b,p_max
def para():
    a, b, p_max = eng.para(K,L,R_min_C,P_max_D,P_max_C,h_CD,h_D,h_CB,h_DB,nargout=3)
    a = np.array(a).reshape((int(K*L),1))
    b = np.array(b).reshape((int(K*L),1))
    p_max = np.array(p_max).reshape((int(K*L),1))
    return a, b, p_max

def binaryPro_oracle(K0,L0,R_min_C0,P_max_D0,P_max_C0,h_CD0,h_D0,h_CB0,h_DB0,index): 
    global K,L,R_min_C,P_max_D,P_max_C,h_CD,h_D,h_CB,h_DB
    K = float(K0)
    L = float(L0)
    R_min_C = float(R_min_C0)
    P_max_D = float(P_max_D0)
    P_max_C = float(P_max_C0)
    h_CD = matlab.double(h_CD0.tolist())
    h_CD.reshape((K0,L0))
    h_D = matlab.double(h_D0.tolist())
    h_D.reshape((L0,1))
    h_CB = matlab.double(h_CB0.tolist())
    h_CB.reshape((K0,1))
    h_DB = matlab.double(h_DB0.tolist())
    h_DB.reshape((L0,1))

    global a, b, p_max
    a, b, p_max = para()

    global globallower 
    global globalrho_opt 
    global globalnode_opt 
    global sol_found 

    sol_found = 0

    maxdepth = K*L
    root_flag = 1
    feature_flag = 1


    tolerance = 1.0E-3  	
    globallower = -sys.maxsize
    depthincrease = 0

    root = TreeNode(np.array([]), 0) # root node
    nodeStack = [] 
    nodeList = [] 
    nodeStack.append(root) 
    
    while(len(nodeStack) > 0):
        node = nodeStack.pop(-1) 	# pop out a node
        nodeList.append(node) # save it to nodeList


        print("pop node...")
        print("node.depth:", node.depth)
        print("node.rho_d:" ,node.rho_d)
        depthincrease += 1 
        node.setPlungeDepth(depthincrease)# Inside: node.plunge_depth = node.plunge_depth + depthincrease

        
        resPath = 'data_'+str(K0)+'_'+str(L0)+'/oracle/problem' + str(index) + '_result.txt'
        resFile = open(resPath, mode='r')
        solved = 0 # whether this problem has been solved or not
        line_temp = resFile.readline()
        while line_temp:
            if str(node.rho_d) in line_temp:
                solved = 1
                break
            else:
                line_temp = resFile.readline()
        resFile.close()
        if solved == 0:  # this problem has not been solved
            resPath = 'data_'+str(K0)+'_'+str(L0)+'/oracle/problem' + str(index) + '_result.txt'
            resFile = open(resPath, mode='a+')
            node.rho_opt,node.p,node.upper,node.exitflag = minlp_solve(node) # solve relaxed problem
            resFile.writelines([str(node.rho_d),'\t', str(node.rho_opt).replace("\n"," "), '\t', str(node.p).replace("\n"," "), '\t',
                str(node.upper), '\t',str(node.exitflag),'\n'])
            resFile.close()
        else:  # this problem has been solved
            temp=(line_temp.strip()).split('\t')
            rho_d2 = temp[1]
            temp_a = re.findall(r'[[](.*)[]]', temp[1].strip( ))
            node.rho_opt = np.array(list(map(eval, temp_a[0].split())))
            temp_a = re.findall(r'[[](.*)[]]', temp[2].strip())
            node.p = np.array(list(map(eval, temp_a[0].split())))
            node.upper = float(temp[3])
            node.exitflag = float(temp[4])

        if root_flag == 1:
            root_bound = node.upper
            root_flag = 0
        node.estobj = root_bound - node.upper
        node.global_lower_bound = globallower # save global lower bound
        
        
        ind = node.rho_d.size
        if ind == K0 * L0: # leaf node
            node.leaf = 1
        else:
            rho_d_k = math.ceil(ind/L)
            if rho_d_k!=0:
                rho_d_l = int(ind-(rho_d_k-1)*L)
            else:
                rho_d_l = 0
            if node.depth ==0:
                line_ind = 1
            else:
                line_ind = int((rho_d_k-1)*L+rho_d_l)
            node.power = K*L*p_max[line_ind]/p_max.sum()
            node.channel = math.log(1+1/(a[line_ind]+b[line_ind]),2)/R_min_C


        optPath = 'data_'+str(K0)+'_'+str(L0)+'/oracle/problem' + str(index) + '_optimal.txt'
        optFile = open(optPath, mode='r')
        line_temp = optFile.readline()
        while line_temp:
            if str(node.rho_d) in line_temp:
                node.status = 1
                break
            else:
                line_temp = optFile.readline()
        optFile.close()
            

        if node.exitflag < 0 : # no feasible solution
            print("Infeasible...")
            node.fathomed_flag = 1 # pruned by orignal prune policy
        elif node.exitflag == 0 : # optimal solution is not found
            print("MINLP solver stopped...")
            ind = node.rho_d.size
            node.upper = node.parent.upper
            if ind == K0 * L0 or node.upper < globallower: 
                node.fathomed_flag = 1 # pruned by orignal prune policy
                print("Pruning...")
            else: # directly branch on the next varaible
                print("Branching variable index:%d" %ind)
                rho_d1 = np.append(node.rho_opt[0:ind].copy(),1)
                while rho_d1.size % L0 !=0:
                    rho_d1 = np.append(rho_d1,0)
                rho_d0 = np.append(node.rho_opt[0:ind].copy(),0)
                
                # generate child nodes
                node1 = TreeNode(rho_d1,node.depth+1)
                node0 = TreeNode(rho_d0,node.depth+1)
                node1.parent = node
                node0.parent = node
                node1.branch = 1
                
                if node.rho_opt[ind] > 1/L: # branch on 1, first put node0 and then node1
                    nodeStack.append(node0)
                    nodeStack.append(node1)
                else: # branch on 0, first put node1 and then node0
                    nodeStack.append(node1)
                    nodeStack.append(node0)
        else:# optimal solution is found
            if node.upper < globallower: # local upper bound < global lower bound
                print("Pruning...")
                node.fathomed_flag = 1 # pruned by orignal prune policy
            elif all(((x-math.floor(x))<tolerance or (math.ceil(x)-x)<tolerance) for x in node.rho_opt): 
                # an integer solution is found
                sol_found = sol_found + 1

                node.rho_d = node.rho_opt.round() 
                resFile = open(resPath, mode='r')
                solved = 0 # whether this problem has been solved or not
                line_temp = resFile.readline()
                while line_temp:
                    if str(node.rho_d) in line_temp:
                        solved = 1
                        break
                    else:
                        line_temp = resFile.readline()
                resFile.close()
                if solved == 0:  # this problem has not been solved
                    resPath = 'data_'+str(K0)+'_'+str(L0)+'/oracle/problem' + str(index) + '_result.txt'
                    resFile = open(resPath, mode='a+')
                    node.rho_opt,node.p,node.upper,node.exitflag = minlp_solve(node) # solve relaxed problem
                    resFile.writelines([str(node.rho_d),'\t', str(node.rho_opt).replace("\n"," "), '\t', str(node.p).replace("\n"," "), '\t',
                        str(node.upper), '\t',str(node.exitflag),'\n'])
                    resFile.close()
                else:  # this problem has been solved
                    temp=(line_temp.strip()).split('\t')
                    temp_a = re.findall(r'[[](.*)[]]', temp[1].strip( ))
                    node.rho_opt = np.array(list(map(eval, temp_a[0].split())))
                    temp_a = re.findall(r'[[](.*)[]]', temp[2].strip())
                    node.p = np.array(list(map(eval, temp_a[0].split())))
                    node.upper = float(temp[3])
                    node.exitflag = float(temp[4])

                node.fathomed_flag = 1 # pruned by orignal prune policy
                node.rho_opt = node.rho_opt.round() 
                print("Found integer solution...")
                if node.upper>globallower :
                    print("Updating gloabel lower bound...")
                    globallower = node.upper
                    globalrho_opt = node.rho_opt
                    globalnode_opt = node
                    node.global_lower_bound = globallower
                    print("global lower bound:",globallower)
                    print("gloabl optimal solution:")
                    print(node.rho_opt)
            node.solfound = sol_found
            node.gapobj = node.upper - globallower
            feature_tmp = np.array([node.depth/maxdepth,node.upper/root_bound,node.global_lower_bound/root_bound,node.plunge_depth/maxdepth,
                        node.solfound/maxdepth,node.branch,node.power,node.channel])
            label_tmp = np.array([node.status])

            if node.fathomed_flag != 1:
                wePath = 'data_'+str(K0)+'_'+str(L0)+'/weight.txt'
                weFile = open(wePath, mode='a+')
                weFile.writelines([str(5*math.exp(-2.68*node.depth/maxdepth)),'\n'])
                weFile.close()

                if node.status == 1:
                    # write it as "not prune"
                    if feature_flag == 1:
                        feature = feature_tmp
                        label = label_tmp
                        feature_flag = 0
                    else:
                        label = np.hstack((label,label_tmp))
                        feature = np.vstack((feature,feature_tmp))
                    # branch
                    print("Model decide branching:...")
                    ind = [i for i, x in enumerate(node.rho_opt) if (x-math.floor(x))>tolerance and (math.ceil(x)-x)>tolerance][0]

                    for j in range(0,ind):  
                        node.rho_opt[j] = node.rho_opt[j].round()

                    print("Branching variable index:%d" %ind)
                    rho_d1 = np.append(node.rho_opt[0:ind].copy(),1)
                    while rho_d1.size % L0 !=0:
                        rho_d1 = np.append(rho_d1,0)
                    rho_d0 = np.append(node.rho_opt[0:ind].copy(),0)
                
                    # generate child nodes
                    node1 = TreeNode(rho_d1,node.depth+1)
                    node0 = TreeNode(rho_d0,node.depth+1)
                    node1.parent = node
                    node0.parent = node
                    node1.branch = 1

                    if node.rho_opt[ind] > 1/L: # branch on 1, first put node0 and then node1
                        nodeStack.append(node0)
                        nodeStack.append(node1)
                    else: # branch on 0, first put node1 and then node0
                        nodeStack.append(node1)
                        nodeStack.append(node0)
                else:
                    if feature_flag == 1:
                        feature = feature_tmp
                        label = label_tmp
                        feature_flag = 0
                    else:
                        label = np.hstack((label,label_tmp))
                        feature = np.vstack((feature,feature_tmp))


        print('\n')
    
    return label, feature







            

