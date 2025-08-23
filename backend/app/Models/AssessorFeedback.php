<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class AssessorFeedback extends Model
{
    use HasFactory, SoftDeletes;

    protected $table = 'assessor_feedbacks';

    protected $fillable = [
        'id',
        'qualification_id',
        'learner_id',
        'lo_id',
        'comments',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
