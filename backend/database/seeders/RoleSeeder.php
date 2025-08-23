<?php

namespace Database\Seeders;

use App\Models\Role;
use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class RoleSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $roles = [
            ['role_name' => 'Super Admin', 'status' => 'active'],
            ['role_name' => 'Company Admin', 'status' => 'active'],
            ['role_name' => 'Admin', 'status' => 'active'],
            ['role_name' => 'Learner', 'status' => 'active'],
            ['role_name' => 'Assessor', 'status' => 'active'],
            ['role_name' => 'IQA', 'status' => 'active'],
            ['role_name' => 'EQA', 'status' => 'active'],
        ];

        foreach ($roles as $role) {
            $existingRole = Role::where('role_name', $role['role_name'])->first();
            if ($existingRole === null) {
                Role::create($role);
            } else {
                $existingRole->update(['role_name' => $role['role_name']]);
            }
        }
    }
}
